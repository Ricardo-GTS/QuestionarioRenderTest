from django.urls import path

from . import views

app_name = "moderation"

urlpatterns = [
    path("perguntas/<int:question_id>/reportar", views.report_question, name="report_question"),
    path("reportar/fechar", views.close_report_modal, name="close_report_modal"),
    path("admin", views.dashboard, name="dashboard"),
    path("admin/moderacao", views.pending_reports, name="pending_reports"),
    path("admin/moderacao/<int:question_id>/aprovar-remocao", views.approve_removal, name="approve_removal"),
    path("admin/moderacao/<int:question_id>/rejeitar-remocao", views.reject_removal, name="reject_removal"),
    path("admin/removidas", views.removed_list, name="removed_list"),
    path("admin/removidas/<int:question_id>/reativar", views.reactivate_question, name="reactivate_question"),
    path("admin/removidas/<int:question_id>/editar", views.edit_question, name="edit_question"),
    path("admin/removidas/<int:question_id>/cancelar", views.cancel_edit_question, name="cancel_edit_question"),
    path("admin/configuracoes", views.admin_settings, name="admin_settings"),
]
