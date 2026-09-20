"""Admin = email em settings.ADMIN_EMAILS -- sem coluna role, sem auto-promocao.

Porte de backend/app/core/security.py::is_admin_email e app/api/deps.py::get_current_admin.
"""

from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def is_admin_email(email: str) -> bool:
    return bool(email) and email.strip().lower() in settings.ADMIN_EMAILS


def admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_admin_email(request.user.email):
            raise PermissionDenied("Requer acesso de administrador")
        return view_func(request, *args, **kwargs)

    return wrapper
