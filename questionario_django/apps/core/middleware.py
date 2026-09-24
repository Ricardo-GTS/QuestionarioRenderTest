from django.db import connection
from django.shortcuts import redirect, render

from .permissions import is_admin_email
from .semesters import pick_semester

# Rotas que funcionam sem semestre nenhum aberto (conta, login, infraestrutura).
SEMESTER_FREE_PREFIXES = (
    "/entrar",
    "/registrar",
    "/sair",
    "/auth/",
    "/conta",
    "/senha/",
    "/health",
    "/django-admin/",
    "/admin/semestres",
    "/static/",
)


class SemesterMiddleware:
    """Escolhe o schema do semestre da requisicao (aluno: o ativo; admin: o selecionado
    no painel) e faz connection.set_tenant(). Precisa rodar em TODA requisicao: a
    conexao e' reaproveitada entre requests e guardaria o schema da anterior."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        connection.set_schema_to_public()
        semester = pick_semester(request)
        request.semester = semester
        if semester is not None:
            connection.set_tenant(semester)
        elif not request.path.startswith(SEMESTER_FREE_PREFIXES):
            user = request.user
            if user.is_authenticated and is_admin_email(user.email):
                return redirect("core:semesters")
            return render(request, "core/no_semester.html", status=503)
        return self.get_response(request)
