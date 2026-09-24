from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


def _redirect(request, target):
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = target
        return response
    return redirect(target)


class RequireRegistrationNumberMiddleware:
    """Usuario logado so' usa o sistema com o perfil completo, nesta ordem:
    1. matricula preenchida (login com Google ou conta anterior ao campo);
    2. vinculo com o semestre ativo (conta de semestre anterior -> "Participar").
    Liberados: a propria tela de cada passo, logout e rotas de infraestrutura."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return self.get_response(request)
        static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        infra = (reverse("accounts:logout"), "/health", "/django-admin/", static_prefix)

        if not user.registration_number:
            target = reverse("accounts:complete_registration_number")
            if not request.path.startswith((target, *infra)):
                return _redirect(request, target)
            return self.get_response(request)

        from apps.core.permissions import is_admin_email
        from apps.core.semesters import is_enrolled

        semester = getattr(request, "semester", None)
        if semester is not None and semester.is_active and not is_admin_email(user.email):
            if not is_enrolled(user, semester):
                target = reverse("accounts:join_semester")
                if not request.path.startswith((target, *infra)):
                    return _redirect(request, target)
        return self.get_response(request)
