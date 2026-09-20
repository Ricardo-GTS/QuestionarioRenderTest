from .permissions import is_admin_email


def admin_flag(request):
    """Expoe is_admin no contexto de todo template, sem nunca expor ADMIN_EMAILS."""
    user = getattr(request, "user", None)
    is_admin = bool(user and user.is_authenticated and is_admin_email(user.email))
    return {"is_admin": is_admin}
