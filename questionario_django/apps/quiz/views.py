"""Quiz de treino: o aluno responde, ve na hora se acertou (e a resposta correta),
e so' avanca quando clica em "Proxima". Estado todo na sessao do servidor:
quiz_question_ids, quiz_answers ({id: bool}), quiz_position (indice da pergunta
atual) e quiz_started_at (vence em 24 h). Resposta e "Proxima" mandam o question_id
da pergunta que estava na tela -- se nao bater com a atual (clique duplo, outra aba),
nada muda e o card da pergunta atual e' devolvido."""

import time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .services import current_position, pick_random_questions, quiz_expired, record_attempt, score_quiz

SESSION_KEYS = ("quiz_question_ids", "quiz_answers", "quiz_position", "quiz_started_at")


def question_answered_in_quiz(request, question_id: int) -> bool:
    """Usado pelos comentarios/reporte: a questao foi respondida no quiz atual?"""
    return str(question_id) in request.session.get("quiz_answers", {})


def _new_quiz(request):
    questions = pick_random_questions(exclude_author_id=request.user.id)
    request.session["quiz_question_ids"] = [q.id for q in questions]
    request.session["quiz_answers"] = {}
    request.session["quiz_position"] = 0
    request.session["quiz_started_at"] = time.time()


def _quiz_in_progress(request) -> bool:
    ids = request.session.get("quiz_question_ids")
    if not ids or quiz_expired(request.session.get("quiz_started_at"), time.time()):
        return False
    return _position(request) < len(ids)


def _position(request) -> int:
    ids = request.session.get("quiz_question_ids", [])
    return current_position(ids, request.session.get("quiz_answers", {}), request.session.get("quiz_position"))


def _current_question(request):
    """Pergunta atual, pulando as que foram apagadas no meio do quiz. None = acabou."""
    from apps.questions.models import Question

    ids = request.session.get("quiz_question_ids", [])
    position = _position(request)
    while position < len(ids):
        question = Question.objects.filter(pk=ids[position]).first()
        if question is not None:
            if request.session.get("quiz_position") != position:
                request.session["quiz_position"] = position
            return question
        # apagada (ex: "Excluir Topico e Questoes") -- sai do quiz
        ids.pop(position)
        request.session["quiz_question_ids"] = ids
    request.session["quiz_position"] = position
    return None


def _card_context(request):
    ids = request.session.get("quiz_question_ids", [])
    if not ids:
        return {"no_questions": True}
    question = _current_question(request)
    if question is None:
        return {"finished": True}
    answers = request.session.get("quiz_answers", {})
    given = answers.get(str(question.id))
    context = {
        "question": question,
        "index": _position(request) + 1,
        "total": len(request.session["quiz_question_ids"]),
        "answered": given is not None,
    }
    if given is not None:
        context.update(
            {
                "given_answer": given,
                "is_correct": given == question.correct_answer,
                "is_last": _position(request) + 1 >= len(request.session["quiz_question_ids"]),
                "comment_count": question.comments.filter(removed=False).count(),
            }
        )
    return context


def _render_card(request):
    context = _card_context(request)
    if context.get("finished"):
        response = HttpResponse()
        response["HX-Redirect"] = reverse("quiz:result")
        return response
    return render(request, "quiz/_question.html", context)


def _posted_question_id(request):
    try:
        return int(request.POST.get("question_id", ""))
    except ValueError:
        return None


@login_required
def start(request):
    if request.GET.get("novo") or not _quiz_in_progress(request):
        _new_quiz(request)
    context = _card_context(request)
    if context.get("finished"):
        return redirect("quiz:result")
    return render(request, "quiz/play.html", context)


@login_required
@require_POST
def answer_question(request):
    if not request.session.get("quiz_question_ids"):
        return redirect("quiz:start")
    question = _current_question(request)
    if question is None:
        return _render_card(request)
    answers = request.session.get("quiz_answers", {})
    # So' grava se for a pergunta que esta na tela e ainda sem resposta (nao da pra
    # responder de novo depois de ver a correta).
    if _posted_question_id(request) == question.id and str(question.id) not in answers:
        answers[str(question.id)] = request.POST.get("answer") == "true"
        request.session["quiz_answers"] = answers
    return _render_card(request)


@login_required
@require_POST
def next_question(request):
    if not request.session.get("quiz_question_ids"):
        return redirect("quiz:start")
    question = _current_question(request)
    if question is None:
        return _render_card(request)
    answered = str(question.id) in request.session.get("quiz_answers", {})
    # So' avanca a partir da pergunta que estava na tela, e so' depois de respondida.
    if answered and _posted_question_id(request) == question.id:
        request.session["quiz_position"] = _position(request) + 1
    return _render_card(request)


@login_required
def result(request):
    from apps.questions.models import Question

    question_ids = request.session.get("quiz_question_ids", [])
    if not question_ids:
        return redirect("quiz:start")

    raw_answers = request.session.get("quiz_answers", {})
    questions = list(Question.objects.filter(pk__in=question_ids))
    questions.sort(key=lambda q: question_ids.index(q.id))
    answers = {int(qid): value for qid, value in raw_answers.items()}

    result_data = score_quiz(questions, answers)
    record_attempt(user_id=request.user.id, score=result_data["score"], total=result_data["total"])

    for key in SESSION_KEYS:
        request.session.pop(key, None)

    return render(request, "quiz/result.html", {"result": result_data})
