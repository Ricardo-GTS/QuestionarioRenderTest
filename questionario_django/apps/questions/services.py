"""Porte de backend/app/services/embeddings.py + similarity.py.

Cliente Ollama sincrono (nao async) -- ver secao "Integracao com Ollama" do plano
de migracao: view Django comum, multiplos workers absorvem o paralelismo.
"""

from dataclasses import dataclass

import httpx
from django.conf import settings
from pgvector.django import CosineDistance

from apps.core.services import get_effective_settings

from .models import Question, QuestionStatus, Topic


class EmbeddingServiceError(Exception):
    pass


def _hash_embedding(text: str) -> list[float]:
    """Modo EMBEDDINGS_DISABLED: vetor deterministico por hash do texto, normalizado
    (vetor valido para a coluna e o indice HNSW, sem NaN do vetor zero)."""
    import hashlib
    import math

    from .models import EMBEDDING_DIM

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values = [(digest[i % len(digest)] + i) % 256 - 127.5 for i in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def get_embedding(text: str) -> list[float]:
    if settings.EMBEDDINGS_DISABLED:
        return _hash_embedding(text)
    try:
        response = httpx.post(
            f"{settings.OLLAMA_HOST}/api/embeddings",
            json={"model": settings.OLLAMA_EMBED_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise EmbeddingServiceError(f"Falha ao gerar embedding: {exc}") from exc

    embedding = data.get("embedding")
    if not embedding:
        raise EmbeddingServiceError("Resposta do Ollama sem campo 'embedding'")
    return embedding


@dataclass
class SimilarQuestion:
    question: Question
    similarity: float


def filter_by_threshold(rows, threshold: float) -> list[SimilarQuestion]:
    """Pura, sem dependencia de DB -- porte literal de app/services/similarity.py."""
    max_distance = 1 - threshold
    return [
        SimilarQuestion(question=question, similarity=1 - distance)
        for question, distance in rows
        if distance <= max_distance
    ]


def find_similar_active_questions(embedding, limit: int = 5) -> list[SimilarQuestion]:
    if settings.EMBEDDINGS_DISABLED:
        return []  # build de teste: aceita qualquer questao
    threshold = get_effective_settings().similarity_threshold
    queryset = (
        Question.objects.filter(status=QuestionStatus.ACTIVE)
        .annotate(distance=CosineDistance("embedding", embedding))
        .order_by("distance")[:limit]
    )
    rows = [(q, q.distance) for q in queryset]
    return filter_by_threshold(rows, threshold)


def list_topic_names() -> list[str]:
    """Uniao do catalogo Topic com os topicos ja usados em perguntas, ordenada."""
    names = set(Topic.objects.values_list("name", flat=True))
    names |= set(Question.objects.values_list("topic", flat=True).distinct())
    return sorted(names, key=str.casefold)


# --- Comentarios ---


def can_view_comments(
    *, is_admin: bool, answered_in_quiz: bool, has_own_visible_comment: bool, is_author: bool = False
) -> bool:
    """Pura. Quem ve (e comenta/reporta) os comentarios de uma questao: admin, o autor da
    questao (pagina Minhas Questoes), quem ja' respondeu a questao no quiz atual, ou quem
    ja' comentou nela (depois do quiz o aluno so' volta as questoes em que comentou)."""
    return is_admin or is_author or answered_in_quiz or has_own_visible_comment


def comments_open(question) -> bool:
    """Pura. Questao removida pelo professor: comentarios so' leitura."""
    return question.status != QuestionStatus.REMOVED


def accuracy_label(answer_count: int, correct_count: int) -> str:
    """Pura. Com menos de MIN_ANSWERS_FOR_ACCURACY respostas a porcentagem nao diz nada."""
    if answer_count == 0:
        return "Ainda não foi respondida"
    times = "1 vez" if answer_count == 1 else f"{answer_count} vezes"
    if answer_count < MIN_ANSWERS_FOR_ACCURACY:
        return f"Respondida {times} (acerto aparece a partir de {MIN_ANSWERS_FOR_ACCURACY} respostas)"
    return f"Respondida {times} · {round(100 * correct_count / answer_count)}% de acerto"


def user_can_view_comments(request, question) -> bool:
    from apps.core.permissions import is_admin_email
    from apps.quiz.views import question_answered_in_quiz

    return can_view_comments(
        is_admin=is_admin_email(request.user.email),
        answered_in_quiz=question_answered_in_quiz(request, question.id),
        has_own_visible_comment=question.comments.filter(author=request.user, removed=False).exists(),
        is_author=question.author_id == request.user.id,
    )


def visible_comments(question):
    return question.comments.filter(removed=False).select_related("author")


def mark_seen(user, question) -> None:
    from django.utils import timezone

    from .models import CommentSeen

    CommentSeen.objects.update_or_create(user=user, question=question, defaults={"last_seen_at": timezone.now()})


def commented_questions_for(user):
    """Questoes (de OUTROS autores -- as proprias ficam em Minhas Questoes) em que o
    usuario tem comentario visivel, com total de comentarios, ultima atividade e quantos
    comentarios de OUTROS chegaram desde a ultima visita (selo "N novos") -- numa query so'."""
    from django.db.models import Count, Exists, F, Max, OuterRef, Q, Subquery

    from .models import CommentSeen, QuestionComment

    seen_at = CommentSeen.objects.filter(user=user, question=OuterRef("pk")).values("last_seen_at")[:1]
    visible = Q(comments__removed=False)
    new_from_others = visible & ~Q(comments__author=user) & (Q(seen_at__isnull=True) | Q(comments__created_at__gt=F("seen_at")))
    return (
        Question.objects.filter(
            Exists(QuestionComment.objects.filter(question=OuterRef("pk"), author=user, removed=False))
        )
        .exclude(author=user)
        .annotate(
            seen_at=Subquery(seen_at),
            comment_count=Count("comments", filter=visible, distinct=True),
            new_count=Count("comments", filter=new_from_others, distinct=True),
            last_activity=Max("comments__created_at", filter=visible),
        )
        .order_by("-last_activity")
    )


def register_comment_report(*, comment, reporter, reason: str) -> str | None:
    """Devolve a mensagem de erro pro usuario, ou None se registrou."""
    from .models import CommentReport

    if comment.author_id == reporter.id:
        return "Você não pode reportar o próprio comentário."
    if CommentReport.objects.filter(comment=comment, reporter=reporter).exists():
        return "Você já reportou este comentário."
    CommentReport.objects.create(comment=comment, reporter=reporter, reason=reason)
    return None


def list_comments_with_pending_reports():
    from .models import CommentReportStatus, QuestionComment

    comments = (
        QuestionComment.objects.filter(reports__status=CommentReportStatus.PENDING)
        .distinct()
        .select_related("author", "question")
        .order_by("created_at")
    )
    return [
        {
            "comment": comment,
            "reports": list(comment.reports.filter(status=CommentReportStatus.PENDING).select_related("reporter")),
        }
        for comment in comments
    ]


def resolve_comment_report(comment, *, remove: bool) -> None:
    """Decisao unica pro comentario e TODOS os reportes pendentes dele (mesmo padrao da
    moderacao de perguntas): remover oculta o comentario e aceita; manter rejeita."""
    from .models import CommentReportStatus

    if remove:
        comment.removed = True
        comment.save(update_fields=["removed"])
    comment.reports.filter(status=CommentReportStatus.PENDING).update(
        status=CommentReportStatus.ACCEPTED if remove else CommentReportStatus.REJECTED
    )


# --- Minhas Questoes (autor acompanha as proprias questoes) ---

MIN_ANSWERS_FOR_ACCURACY = 5
MY_QUESTIONS_FILTERS = {
    "ativas": QuestionStatus.ACTIVE,
    "em-analise": QuestionStatus.REPORTED,
    "removidas": QuestionStatus.REMOVED,
}


def _count(queryset):
    """Subquery de contagem por questao (queryset ja' filtrado por question=OuterRef("pk")).
    Subquery, nao JOIN: juntar comentarios x reportes x respostas multiplicaria as linhas."""
    from django.db.models import Count, IntegerField, Subquery
    from django.db.models.functions import Coalesce

    counted = queryset.order_by().values("question").annotate(c=Count("pk")).values("c")[:1]
    return Coalesce(Subquery(counted, output_field=IntegerField()), 0)


def own_questions_for(user, status=None):
    """Questoes do autor, com todas as contagens anotadas (comentarios, novos de outros
    desde a ultima visita, reportes por situacao, respostas e acertos) e os motivos dos
    reportes num prefetch so' -- sem o reporter (anonimato de quem reportou)."""
    from datetime import datetime
    from datetime import timezone as dt_timezone

    from django.db.models import OuterRef, Prefetch, Subquery, Value
    from django.db.models.functions import Coalesce

    from apps.moderation.models import Report, ReportStatus

    from .models import CommentSeen, QuestionAnswer, QuestionComment

    never = Value(datetime(1970, 1, 1, tzinfo=dt_timezone.utc))
    seen_at = CommentSeen.objects.filter(user=user, question=OuterRef("pk")).values("last_seen_at")[:1]
    comments = QuestionComment.objects.filter(question=OuterRef("pk"), removed=False)
    reports = Report.objects.filter(question=OuterRef("pk"))
    answers = QuestionAnswer.objects.filter(question=OuterRef("pk"))

    queryset = Question.objects.filter(author=user)
    if status is not None:
        queryset = queryset.filter(status=status)
    return (
        queryset.annotate(seen_at=Coalesce(Subquery(seen_at), never))
        .annotate(
            comment_count=_count(comments),
            new_count=_count(comments.exclude(author=user).filter(created_at__gt=OuterRef("seen_at"))),
            pending_reports=_count(reports.filter(status=ReportStatus.PENDING)),
            accepted_reports=_count(reports.filter(status=ReportStatus.ACCEPTED)),
            rejected_reports=_count(reports.filter(status=ReportStatus.REJECTED)),
            answer_count=_count(answers),
            correct_count=_count(answers.filter(is_correct=True)),
        )
        .prefetch_related(
            Prefetch(
                "reports",
                queryset=Report.objects.only("id", "question_id", "reason", "status", "created_at").order_by(
                    "-created_at"
                ),
                to_attr="author_reports",
            )
        )
        .order_by("-created_at", "-id")
    )


def own_questions_status_counts(user) -> dict:
    from django.db.models import Count

    counts = {row["status"]: row["c"] for row in Question.objects.filter(author=user).values("status").annotate(c=Count("id"))}
    return {"todas": sum(counts.values()), **{key: counts.get(status, 0) for key, status in MY_QUESTIONS_FILTERS.items()}}


def new_comments_on_own_questions(user) -> int:
    """Selo do menu: comentarios de OUTROS nas questoes do usuario, depois da ultima vez
    que ele abriu cada uma. Uma query so'."""
    from django.db.models import F, OuterRef, Q, Subquery

    from .models import CommentSeen, QuestionComment

    seen_at = CommentSeen.objects.filter(user=user, question=OuterRef("question")).values("last_seen_at")[:1]
    return (
        QuestionComment.objects.filter(question__author=user, removed=False)
        .exclude(author=user)
        .annotate(seen_at=Subquery(seen_at))
        .filter(Q(seen_at__isnull=True) | Q(created_at__gt=F("seen_at")))
        .count()
    )
