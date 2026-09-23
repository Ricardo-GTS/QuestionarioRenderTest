from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("registrar", views.register, name="register"),
    path("registrar/confirmar", views.confirm_registration, name="confirm_registration"),
    path("registrar/confirmar/reenviar", views.resend_registration_code, name="resend_registration_code"),
    path("entrar", views.login_view, name="login"),
    path("sair", views.logout_view, name="logout"),
    path("senha/recuperar", views.password_reset_request, name="password_reset_request"),
    path("senha/recuperar/codigo", views.password_reset_confirm, name="password_reset_confirm"),
    path("senha/recuperar/reenviar", views.password_reset_resend, name="password_reset_resend"),
    path("auth/google", views.google_login, name="google_login"),
    path("conta", views.account, name="account"),
    path("conta/confirmar-identidade", views.reauth_start, name="reauth_start"),
    path("conta/confirmar-identidade/codigo", views.confirm_reauth, name="confirm_reauth"),
    path("conta/confirmar-identidade/reenviar", views.resend_reauth_code, name="resend_reauth_code"),
    path("conta/confirmar-email", views.confirm_email_change, name="confirm_email_change"),
    path("conta/confirmar-email/reenviar", views.resend_email_change_code, name="resend_email_change_code"),
    path("conta/confirmar-email/cancelar", views.cancel_email_change, name="cancel_email_change"),
    path("conta/matricula", views.complete_registration_number, name="complete_registration_number"),
    path("estatisticas", views.my_stats, name="stats"),
    path("admin/usuarios", views.admin_user_list, name="admin_user_list"),
    path(
        "admin/usuarios/<int:user_id>/matricula",
        views.admin_update_registration_number,
        name="admin_update_registration_number",
    ),
    path("admin/usuarios/<int:user_id>/excluir", views.admin_delete_user, name="admin_delete_user"),
]
