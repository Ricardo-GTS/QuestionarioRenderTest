from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("quiz", views.start, name="start"),
    path("quiz/responder", views.answer_question, name="answer"),
    path("quiz/resultado", views.result, name="result"),
]
