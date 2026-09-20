from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.permissions import admin_required
from apps.core.services import get_effective_settings, update_settings
from apps.questions.models import Question, QuestionStatus
from apps.questions.services import EmbeddingServiceError

from .forms import AppSettingsForm, QuestionEditForm, ReportForm
from .models import Report
from .services import (
    approve_question,
    compute_stats,
    list_questions_by_status,
    list_questions_with_pending_reports,
    register_report,
    resolve_reported_question,
    update_question,
)


def report_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    sent = False
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            if Report.objects.filter(question=question, reporter=request.user).exists():
                form.add_error(None, "Voce ja reportou essa pergunta")
            else:
                register_report(
                    question=question,
                    reporter_id=request.user.id,
                    reason=form.cleaned_data.get("reason") or None,
                    reason_category=form.cleaned_data["reason_category"],
                )
                sent = True
    else:
        form = ReportForm()
    return render(request, "moderation/_report_modal.html", {"form": form, "question": question, "sent": sent})


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
                    category=form.cleaned_data.get("category") or None,
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
                "category": question.category or "",
            }
        )
    return render(request, "moderation/_edit_form.html", {"form": form, "question": question})


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
