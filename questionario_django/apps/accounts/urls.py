from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("registrar", views.register, name="register"),
    path("entrar", views.login_view, name="login"),
    path("sair", views.logout_view, name="logout"),
    path("auth/google", views.google_login, name="google_login"),
    path("conta", views.account, name="account"),
    path("conta/excluir/confirmar", views.delete_account_confirm, name="delete_account_confirm"),
    path("conta/excluir", views.delete_account, name="delete_account"),
    path("estatisticas", views.my_stats, name="stats"),
    path("admin/usuarios", views.admin_user_list, name="admin_user_list"),
    path("admin/usuarios/<int:user_id>/excluir", views.admin_delete_user, name="admin_delete_user"),
]
