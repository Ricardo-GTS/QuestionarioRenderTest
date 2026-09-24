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


def get_embedding(text: str) -> list[float]:
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


def can_view_comments(*, is_admin: bool, answered_in_quiz: bool, has_own_visible_comment: bool) -> bool:
    """Pura. Quem ve (e comenta/reporta) os comentarios de uma questao: admin, quem ja'
    respondeu a questao no quiz atual, ou quem ja' comentou nela (depois do quiz o
    aluno so' volta a ver as questoes em que comentou -- aba Minhas interacoes)."""
    return is_admin or answered_in_quiz or has_own_visible_comment


def user_can_view_comments(request, question) -> bool:
    from apps.core.permissions import is_admin_email
    from apps.quiz.views import question_answered_in_quiz

    return can_view_comments(
        is_admin=is_admin_email(request.user.email),
        answered_in_quiz=question_answered_in_quiz(request, question.id),
        has_own_visible_comment=question.comments.filter(author=request.user, removed=False).exists(),
    )


def visible_comments(question):
    return question.comments.filter(removed=False).select_related("author")


def mark_seen(user, question) -> None:
    from django.utils import timezone

    from .models import CommentSeen

    CommentSeen.objects.update_or_create(user=user, question=question, defaults={"last_seen_at": timezone.now()})


def commented_questions_for(user):
    """Questoes em que o usuario tem comentario visivel, com total de comentarios,
    ultima atividade e quantos comentarios de OUTROS chegaram desde a ultima visita
    (selo "N novos") -- tudo anotado numa query so'."""
    from django.db.models import Count, Exists, F, Max, OuterRef, Q, Subquery

    from .models import CommentSeen, QuestionComment

    seen_at = CommentSeen.objects.filter(user=user, question=OuterRef("pk")).values("last_seen_at")[:1]
    visible = Q(comments__removed=False)
    new_from_others = visible & ~Q(comments__author=user) & (Q(seen_at__isnull=True) | Q(comments__created_at__gt=F("seen_at")))
    return (
        Question.objects.filter(
            Exists(QuestionComment.objects.filter(question=OuterRef("pk"), author=user, removed=False))
        )
        .annotate(
            seen_at=Subquery(seen_at),
            comment_count=Count("comments", filter=visible, distinct=True),
            new_count=Count("comments", filter=new_from_others, distinct=True),
            last_activity=Max("comments__created_at", filter=visible),
        )
        .order_by("-last_activity")
    )


def register_comment_report(*, comment, reporter, reason_category: str, reason) -> str | None:
    """Devolve a mensagem de erro pro usuario, ou None se registrou."""
    from .models import CommentReport

    if comment.author_id == reporter.id:
        return "Você não pode reportar o próprio comentário."
    if CommentReport.objects.filter(comment=comment, reporter=reporter).exists():
        return "Você já reportou este comentário."
    CommentReport.objects.create(comment=comment, reporter=reporter, reason_category=reason_category, reason=reason)
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
