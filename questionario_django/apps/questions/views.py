from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from . import services
from .forms import NEW_TOPIC_CHOICE, QuestionForm
from .models import Question


@login_required
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
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
