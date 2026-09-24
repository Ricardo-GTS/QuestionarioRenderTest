from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.core import ratelimits as rl

from . import services
from .forms import NEW_TOPIC_CHOICE, CommentForm, CommentReportForm, QuestionForm
from .models import Question, QuestionComment


@login_required
@ratelimit(key="ip", rate=rl.QUESTION_IP_CEILING, method="POST", block=True, group="question-ip")
@ratelimit(key="user_or_ip", rate=rl.QUESTION_PER_USER, method="POST", block=True, group="question-user")
def create_question(request):
    similar_questions = []
    success_message = None
    error_message = None
    form = QuestionForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            embedding = services.get_embedding(form.cleaned_data["statement"])
        except services.EmbeddingServiceError:
            error_message = "Servico de embeddings indisponivel, tente novamente em instantes."
        else:
            similar_questions = services.find_similar_active_questions(embedding)
            if not similar_questions:
                Question.objects.create(
                    author=request.user,
                    statement=form.cleaned_data["statement"],
                    correct_answer=form.cleaned_data["correct_answer"],
                    topic=form.cleaned_data["topic"],
                    citations_references=form.cleaned_data["citations_references"],
                    pertinence=form.cleaned_data["pertinence"],
                    embedding=embedding,
                )
                success_message = "Pergunta criada com sucesso."
                form = QuestionForm()

    context = {
        "form": form,
        "similar_questions": similar_questions,
        "success_message": success_message,
        "error_message": error_message,
        "new_topic_choice": NEW_TOPIC_CHOICE,
    }
    if request.headers.get("HX-Request"):
        return render(request, "questions/_form.html", context)
    return render(request, "questions/create.html", context)


# --- Comentarios (painel dentro do card da questao: quiz e Minhas interacoes) ---


def _comments_panel_context(request, question, form=None):
    from apps.core.permissions import is_admin_email

    from .models import CommentReport

    comments = list(services.visible_comments(question))
    reported_ids = set(
        CommentReport.objects.filter(reporter=request.user, comment__in=comments).values_list("comment_id", flat=True)
    )
    return {
        "question": question,
        "comments": comments,
        "reported_ids": reported_ids,
        "is_admin": is_admin_email(request.user.email),
        "form": form or CommentForm(),
    }


@login_required
@ratelimit(key="user", rate=rl.COMMENT_PER_USER, method="POST", block=True, group="comment-create")
def comments_panel(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if not services.user_can_view_comments(request, question):
        raise PermissionDenied("Responda a questão para ver os comentários")
    form = None
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            QuestionComment.objects.create(question=question, author=request.user, text=form.cleaned_data["text"])
            form = None
    services.mark_seen(request.user, question)
    return render(request, "questions/_comments_panel.html", _comments_panel_context(request, question, form))


@login_required
@require_POST
def delete_comment(request, comment_id):
    """Autor apaga o proprio (some de vez); admin oculta qualquer um (removed=True,
    fica guardado pro historico de reportes)."""
    from apps.core.permissions import is_admin_email

    comment = get_object_or_404(QuestionComment, pk=comment_id, removed=False)
    question = comment.question
    if comment.author_id == request.user.id:
        comment.delete()
    elif is_admin_email(request.user.email):
        comment.removed = True
        comment.save(update_fields=["removed"])
    else:
        raise PermissionDenied("So' o autor ou o admin apagam o comentario")
    if not services.user_can_view_comments(request, question):
        # Era o unico comentario dele e ele nao esta respondendo essa questao no quiz agora.
        return HttpResponse('<p class="chip chip--neutral">Comentário apagado.</p>')
    return render(request, "questions/_comments_panel.html", _comments_panel_context(request, question))


@login_required
@ratelimit(key="user", rate=rl.COMMENT_REPORT_PER_USER, method="POST", block=True, group="comment-report")
def report_comment(request, comment_id):
    comment = get_object_or_404(QuestionComment.objects.select_related("question"), pk=comment_id, removed=False)
    if not services.user_can_view_comments(request, comment.question):
        raise PermissionDenied("Sem acesso aos comentarios dessa questao")
    error = None
    sent = False
    if request.method == "POST":
        form = CommentReportForm(request.POST)
        if form.is_valid():
            error = services.register_comment_report(
                comment=comment,
                reporter=request.user,
                reason_category=form.cleaned_data["reason_category"],
                reason=(form.cleaned_data.get("reason") or "").strip() or None,
            )
            sent = error is None
    else:
        form = CommentReportForm()
    return render(
        request,
        "questions/_comment_report_form.html",
        {"comment": comment, "form": form, "error": error, "sent": sent, "cancelled": bool(request.GET.get("cancelar"))},
    )
