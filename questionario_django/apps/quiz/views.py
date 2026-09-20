from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .services import pick_random_questions, record_attempt, score_quiz


def _current_question_context(request):
    from apps.questions.models import Question

    question_ids = request.session.get("quiz_question_ids", [])
    answers = request.session.get("quiz_answers", {})
    total = len(question_ids)
    answered = len(answers)

    if total == 0:
        return {"no_questions": True}

    current_id = question_ids[answered]
    question = Question.objects.get(pk=current_id)
    return {"question": question, "index": answered + 1, "total": total}


@login_required
def start(request):
    questions = pick_random_questions(exclude_author_id=request.user.id)
    request.session["quiz_question_ids"] = [q.id for q in questions]
    request.session["quiz_answers"] = {}
    return render(request, "quiz/play.html", _current_question_context(request))


@login_required
def answer_question(request):
    if request.method != "POST":
        return redirect("quiz:start")

    question_ids = request.session.get("quiz_question_ids", [])
    answers = request.session.get("quiz_answers", {})

    if not question_ids or len(answers) >= len(question_ids):
        return redirect("quiz:result")

    current_id = question_ids[len(answers)]
    answers[str(current_id)] = request.POST.get("answer") == "true"
    request.session["quiz_answers"] = answers
    request.session.modified = True

    if len(answers) >= len(question_ids):
        response = HttpResponse()
        response["HX-Redirect"] = reverse("quiz:result")
        return response

    return render(request, "quiz/_question.html", _current_question_context(request))


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

    request.session.pop("quiz_question_ids", None)
    request.session.pop("quiz_answers", None)

    return render(request, "quiz/result.html", {"result": result_data})
