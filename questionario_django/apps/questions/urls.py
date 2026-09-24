from django.urls import path

from . import views

app_name = "questions"

urlpatterns = [
    path("", views.create_question, name="create"),
    path("minhas-questoes", views.my_questions, name="mine"),
    path("perguntas/<int:question_id>/comentarios", views.comments_panel, name="comments_panel"),
    path("comentarios/<int:comment_id>/apagar", views.delete_comment, name="delete_comment"),
    path("comentarios/<int:comment_id>/reportar", views.report_comment, name="report_comment"),
]
