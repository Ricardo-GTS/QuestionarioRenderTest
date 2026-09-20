from django.db import connection
from django.http import HttpResponse, JsonResponse

import httpx
from django.conf import settings


def health(request):
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        response = httpx.get(settings.OLLAMA_HOST, timeout=5.0)
        checks["ollama"] = "ok" if response.status_code < 500 else "degraded"
    except Exception:
        checks["ollama"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return JsonResponse({"status": status, "checks": checks})


def rate_limited(request, exception=None):
    return HttpResponse("Muitas requisicoes -- tente novamente em instantes.", status=429)
