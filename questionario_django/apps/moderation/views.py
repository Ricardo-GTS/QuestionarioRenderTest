from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import admin_required
from apps.core.services import get_effective_settings, update_settings
from apps.questions.forms import NEW_TOPIC_CHOICE
from apps.questions.models import Question, QuestionStatus
from apps.questions.services import EmbeddingServiceError

from .forms import AppSettingsForm, QuestionEditForm, ReportForm
from .models import Report
from .services import (
    TopicError,
    approve_question,
    compute_stats,
    create_topic,
    delete_topic,
    list_topics_with_counts,
    list_questions_by_status,
    list_questions_with_pending_reports,
    register_report,
    rename_topic,
    resolve_reported_question,
    update_question,
)


@login_required
def report_question(request, question_id):
    """Modal (pagina de resultado) ou painel dentro do card do quiz (?painel=1 / campo
    hidden "painel"). O painel so' abre pra questao ja' respondida no quiz atual."""
    from apps.core.permissions import is_admin_email
    from apps.quiz.views import question_answered_in_quiz

    question = get_object_or_404(Question, pk=question_id)
    panel = bool(request.GET.get("painel") or request.POST.get("painel"))
    if panel and not (question_answered_in_quiz(request, question.id) or is_admin_email(request.user.email)):
        raise PermissionDenied("Responda a questao antes de reportar")
    template = "moderation/_report_panel.html" if panel else "moderation/_report_modal.html"
    already_reported = Report.objects.filter(question=question, reporter=request.user).exists()
    sent = False
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            if Report.objects.filter(question=question, reporter=request.user).exists():
                form.add_error(None, "Você já reportou essa pergunta")
            else:
                register_report(
                    question=question,
                    reporter_id=request.user.id,
                    reason=form.cleaned_data["reason"],
                )
                sent = True
    else:
        form = ReportForm()
    return render(
        request,
        template,
        {"form": form, "question": question, "sent": sent, "already_reported": already_reported and not sent},
    )


def close_report_modal(request):
    return HttpResponse("")


@admin_required
def dashboard(request):
    stats = compute_stats()
    return render(request, "moderation/dashboard.html", {"stats": stats})


@admin_required
def pending_reports(request):
    items = list_questions_with_pending_reports()
    return render(request, "moderation/pending.html", {"items": items})


@admin_required
@require_POST
def approve_removal(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    resolve_reported_question(question, approve_removal=True)
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("moderation:pending_reports")


@admin_required
@require_POST
def reject_removal(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    resolve_reported_question(question, approve_removal=False)
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("moderation:pending_reports")


@admin_required
def removed_list(request):
    questions = list_questions_by_status(QuestionStatus.REMOVED)
    return render(request, "moderation/removed.html", {"questions": questions})


@admin_required
@require_POST
def reactivate_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    approve_question(question)
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("moderation:removed_list")


@admin_required
def edit_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if request.method == "POST":
        form = QuestionEditForm(request.POST)
        if form.is_valid():
            try:
                update_question(
                    question,
                    statement=form.cleaned_data["statement"],
                    correct_answer=form.cleaned_data["correct_answer"],
                    topic=form.cleaned_data["topic"],
                    citations_references=form.cleaned_data["citations_references"],
                    pertinence=form.cleaned_data["pertinence"],
                )
            except EmbeddingServiceError:
                form.add_error(None, "Servico de embeddings indisponivel, tente novamente.")
            else:
                return render(request, "moderation/_question_row.html", {"question": question})
    else:
        form = QuestionEditForm(
            initial={
                "statement": question.statement,
                "correct_answer": "true" if question.correct_answer else "false",
                "topic": question.topic,
                "citations_references": question.citations_references,
                "pertinence": question.pertinence,
            }
        )
    return render(
        request,
        "moderation/_edit_form.html",
        {"form": form, "question": question, "new_topic_choice": NEW_TOPIC_CHOICE},
    )


@admin_required
def cancel_edit_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    return render(request, "moderation/_question_row.html", {"question": question})


@admin_required
def admin_settings(request):
    current = get_effective_settings()
    error = None
    if request.method == "POST":
        form = AppSettingsForm(request.POST)
        if form.is_valid():
            try:
                update_settings(
                    similarity_threshold=form.cleaned_data["similarity_threshold"],
                    quiz_size=form.cleaned_data["quiz_size"],
                    report_threshold=form.cleaned_data["report_threshold"],
                )
            except ValueError as exc:
                error = str(exc)
            else:
                return redirect("moderation:admin_settings")
    else:
        form = AppSettingsForm(
            initial={
                "similarity_threshold": current.similarity_threshold,
                "quiz_size": current.quiz_size,
                "report_threshold": current.report_threshold,
            }
        )
    return render(request, "moderation/settings.html", {"form": form, "error": error})


def _render_topic_list(request, error=None):
    return render(request, "moderation/topics.html", {"topics": list_topics_with_counts(), "error": error})


@admin_required
def topic_list(request):
    return _render_topic_list(request)


@admin_required
@require_POST
def topic_create(request):
    try:
        create_topic(request.POST.get("name", ""))
    except TopicError as exc:
        return _render_topic_list(request, error=str(exc))
    return redirect("moderation:topic_list")


@admin_required
@require_POST
def topic_rename(request):
    try:
        rename_topic(request.POST.get("topic", ""), request.POST.get("new_name", ""))
    except TopicError as exc:
        return _render_topic_list(request, error=str(exc))
    return redirect("moderation:topic_list")


@admin_required
@require_POST
def topic_delete(request):
    try:
        delete_topic(
            request.POST.get("topic", ""),
            reassign_to=request.POST.get("reassign_to") or None,
            delete_questions=request.POST.get("mode") == "delete_questions",
        )
    except TopicError as exc:
        return _render_topic_list(request, error=str(exc))
    return redirect("moderation:topic_list")


@admin_required
def pending_comment_reports(request):
    from apps.questions.services import list_comments_with_pending_reports

    return render(request, "moderation/comment_reports.html", {"items": list_comments_with_pending_reports()})


def _resolve_comment(request, comment_id, *, remove):
    from apps.questions.models import QuestionComment
    from apps.questions.services import resolve_comment_report

    comment = get_object_or_404(QuestionComment, pk=comment_id)
    resolve_comment_report(comment, remove=remove)
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("moderation:pending_comment_reports")


@admin_required
@require_POST
def remove_reported_comment(request, comment_id):
    return _resolve_comment(request, comment_id, remove=True)


@admin_required
@require_POST
def keep_reported_comment(request, comment_id):
    return _resolve_comment(request, comment_id, remove=False)
