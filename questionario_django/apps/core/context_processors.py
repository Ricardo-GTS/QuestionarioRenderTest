from .permissions import is_admin_email


def admin_flag(request):
    """Expoe is_admin no contexto de todo template, sem nunca expor ADMIN_EMAILS, e,
    pro admin, o seletor de semestre (lista + o que ele esta vendo)."""
    user = getattr(request, "user", None)
    is_admin = bool(user and user.is_authenticated and is_admin_email(user.email))
    context = {"is_admin": is_admin, "current_semester": getattr(request, "semester", None)}
    if is_admin and not request.headers.get("HX-Request"):
        from .models import Semester

        context["all_semesters"] = list(Semester.objects.only("id", "name", "is_active"))
    return context
