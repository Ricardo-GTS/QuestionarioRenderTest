from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse


class RequireRegistrationNumberMiddleware:
    """Usuario logado sem matricula (login com Google ou conta anterior ao campo)
    so' acessa a tela de completar a matricula, o logout e rotas de infraestrutura."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not user.registration_number:
            target = reverse("accounts:complete_registration_number")
            static_prefix = "/" + settings.STATIC_URL.lstrip("/")
            allowed = (target, reverse("accounts:logout"), "/health", "/django-admin/", static_prefix)
            if not request.path.startswith(allowed):
                if request.headers.get("HX-Request"):
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = target
                    return response
                return redirect(target)
        return self.get_response(request)
