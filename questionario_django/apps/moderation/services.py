"""Porte de backend/app/services/moderation.py + stats.py."""

from django.db import transaction
from django.db.models import Count

from apps.core.services import get_effective_settings

from .models import Report, ReportStatus


def should_flag(report_count: int, threshold: int, current_status: str) -> bool:
    """Pura, sem dependencia de DB -- porte literal de app/services/moderation.py."""
    from apps.questions.models import QuestionStatus

    return report_count >= threshold and current_status == QuestionStatus.ACTIVE


def register_report(*, question, reporter_id: int, reason: str) -> Report:
    from apps.questions.models import QuestionStatus

    report = Report.objects.create(
        question=question, reporter_id=reporter_id, reason=reason
    )
    report_count = Report.objects.filter(question=question).count()
    threshold = get_effective_settings().report_threshold
    if should_flag(report_count, threshold, question.status):
        question.status = QuestionStatus.REPORTED
        question.save(update_fields=["status"])
    return report


def list_questions_by_status(status_filter: str):
    from apps.questions.models import Question

    return list(Question.objects.filter(status=status_filter).select_related("author").order_by("-created_at"))


def list_questions_with_pending_reports():
    """Fila de moderacao: perguntas com PELO MENOS 1 report pendente, independente
    do status da pergunta -- de proposito, ver CLAUDE.md/plano de migracao."""
    from apps.questions.models import Question

    questions = (
        Question.objects.filter(reports__status=ReportStatus.PENDING)
        .distinct()
        .select_related("author")
        .order_by("created_at")
    )
    result = []
    for question in questions:
        pending = list(question.reports.filter(status=ReportStatus.PENDING).select_related("reporter"))
        result.append({"question": question, "reports": pending})
    return result


def approve_question(question) -> None:
    """Reativa uma pergunta removida sem mexer nos reports (ja resolvidos antes)."""
    from apps.questions.models import QuestionStatus

    question.status = QuestionStatus.ACTIVE
    question.save(update_fields=["status"])


def resolve_reported_question(question, *, approve_removal: bool) -> None:
    """Decisao unica: pergunta + TODOS os reports pendentes dela de uma vez."""
    from apps.questions.models import QuestionStatus

    question.status = QuestionStatus.REMOVED if approve_removal else QuestionStatus.ACTIVE
    question.save(update_fields=["status"])
    new_report_status = ReportStatus.ACCEPTED if approve_removal else ReportStatus.REJECTED
    Report.objects.filter(question=question, status=ReportStatus.PENDING).update(status=new_report_status)


def update_question(
    question, *, statement=None, correct_answer=None, topic=None, citations_references=None, pertinence=None
):
    from apps.questions.services import get_embedding

    statement_changed = statement is not None and statement != question.statement
    if statement is not None:
        question.statement = statement
    if correct_answer is not None:
        question.correct_answer = correct_answer
    if topic is not None:
        question.topic = topic
    if citations_references is not None:
        question.citations_references = citations_references
    if pertinence is not None:
        question.pertinence = pertinence
    if statement_changed:
        question.embedding = get_embedding(question.statement)
    question.save()
    return question


class TopicError(ValueError):
    pass


def list_topics_with_counts() -> list[dict]:
    """Todos os topicos (catalogo + usados em perguntas), com quantas perguntas usam cada um."""
    from apps.questions.models import Question
    from apps.questions.services import list_topic_names

    counts = {row["topic"]: row["c"] for row in Question.objects.values("topic").annotate(c=Count("id"))}
    return [{"name": name, "count": counts.get(name, 0)} for name in list_topic_names()]


def create_topic(name: str) -> None:
    from apps.questions.models import Topic
    from apps.questions.services import list_topic_names

    name = name.strip()
    if not name:
        raise TopicError("Digite o nome do tópico.")
    if name in list_topic_names():
        raise TopicError(f"O tópico '{name}' já existe.")
    Topic.objects.create(name=name)


@transaction.atomic
def rename_topic(old_name: str, new_name: str) -> None:
    """Renomeia no catalogo e em todas as perguntas que usam o topico. Renomear para
    um nome ja existente e' recusado -- mesclar e' feito via delete_topic(reassign_to=...)."""
    from apps.questions.models import Question, Topic
    from apps.questions.services import list_topic_names

    new_name = new_name.strip()
    names = list_topic_names()
    if old_name not in names:
        raise TopicError(f"O tópico '{old_name}' não existe.")
    if not new_name:
        raise TopicError("Digite o novo nome do tópico.")
    if new_name == old_name:
        return
    if new_name in names:
        raise TopicError(
            f"O tópico '{new_name}' já existe. Para juntar os dois, exclua '{old_name}' "
            f"movendo as perguntas para '{new_name}'."
        )
    Question.objects.filter(topic=old_name).update(topic=new_name)
    Topic.objects.filter(name=old_name).delete()
    Topic.objects.create(name=new_name)


@transaction.atomic
def delete_topic(name: str, *, reassign_to: str | None = None, delete_questions: bool = False) -> None:
    """Exclui o topico. Se houver perguntas usando, e' preciso escolher o destino delas:
    reassign_to (move para outro topico existente) ou delete_questions=True (apaga as
    perguntas junto -- hard delete, os reports delas vao em cascata)."""
    from apps.questions.models import Question, Topic
    from apps.questions.services import list_topic_names

    names = list_topic_names()
    if name not in names:
        raise TopicError(f"O tópico '{name}' não existe.")
    questions = Question.objects.filter(topic=name)
    if delete_questions:
        questions.delete()
    elif questions.exists():
        if not reassign_to:
            raise TopicError(
                f"Há perguntas usando '{name}'. Escolha para qual tópico movê-las antes de excluir."
            )
        if reassign_to == name or reassign_to not in names:
            raise TopicError("Escolha um tópico de destino válido e diferente do excluído.")
        questions.update(topic=reassign_to)
    Topic.objects.filter(name=name).delete()

def compute_average_score_percent(attempts) -> float | None:
    """Pura -- porte literal de app/services/stats.py. attempts: list[tuple[score, total]]."""
    ratios = [score / total for score, total in attempts if total > 0]
    if not ratios:
        return None
    return sum(ratios) / len(ratios) * 100


def compute_user_reputation(user_id: int) -> dict:
    from apps.questions.models import Question, QuestionStatus

    return {
        "accepted_reports_count": Report.objects.filter(reporter_id=user_id, status=ReportStatus.ACCEPTED).count(),
        "rejected_reports_count": Report.objects.filter(reporter_id=user_id, status=ReportStatus.REJECTED).count(),
        "questions_removed_count": Question.objects.filter(
            author_id=user_id, status=QuestionStatus.REMOVED
        ).count(),
    }


def compute_all_users_reputation() -> dict[int, dict]:
    from apps.questions.models import Question, QuestionStatus

    accepted = {
        row["reporter_id"]: row["c"]
        for row in Report.objects.filter(status=ReportStatus.ACCEPTED).values("reporter_id").annotate(c=Count("id"))
    }
    rejected = {
        row["reporter_id"]: row["c"]
        for row in Report.objects.filter(status=ReportStatus.REJECTED).values("reporter_id").annotate(c=Count("id"))
    }
    removed = {
        row["author_id"]: row["c"]
        for row in Question.objects.filter(status=QuestionStatus.REMOVED).values("author_id").annotate(c=Count("id"))
    }
    user_ids = set(accepted) | set(rejected) | set(removed)
    return {
        uid: {
            "accepted_reports_count": accepted.get(uid, 0),
            "rejected_reports_count": rejected.get(uid, 0),
            "questions_removed_count": removed.get(uid, 0),
        }
        for uid in user_ids
    }


def compute_stats() -> dict:
    from apps.accounts.models import User
    from apps.questions.models import Question
    from apps.quiz.models import QuizAttempt

    questions_by_status = {row["status"]: row["c"] for row in Question.objects.values("status").annotate(c=Count("id"))}
    attempts = list(QuizAttempt.objects.values_list("score", "total"))

    questions_by_topic = [
        {"topic": row["topic"], "count": row["c"]}
        for row in Question.objects.values("topic").annotate(c=Count("id")).order_by("-c")
    ]

    return {
        "total_users": User.objects.count(),
        "total_reports": Report.objects.count(),
        "active_questions": questions_by_status.get("active", 0),
        "reported_questions": questions_by_status.get("reported", 0),
        "removed_questions": questions_by_status.get("removed", 0),
        "total_quiz_attempts": len(attempts),
        "average_score_percent": compute_average_score_percent(attempts),
        "questions_by_topic": questions_by_topic,
    }
