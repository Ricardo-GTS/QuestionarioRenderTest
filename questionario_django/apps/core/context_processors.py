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


# Secao do menu pela rota (url_name/namespace) -- marca o item atual na barra do topo
# (computador) e na barra de baixo (celular). "perfil" agrupa o que no celular fica
# dentro da aba Perfil.
_ADMIN_URLS = {"semesters", "admin_user_list"}
_PROFILE_URLS = {"profile", "account", "interactions", "stats", "confirm_reauth", "confirm_email_change"}


def nav_section(request):
    match = getattr(request, "resolver_match", None)
    if match is None:
        return {"nav": ""}
    namespace, name = match.namespace, match.url_name
    if namespace == "quiz":
        section = "treinar"
    elif name == "create":
        section = "criar"
    elif name == "mine":
        section = "minhas"
    elif namespace == "moderation" and name not in {"report_question", "close_report_modal"} or name in _ADMIN_URLS:
        section = "admin"
    elif name in _PROFILE_URLS:
        section = name if name in {"interactions", "stats"} else "perfil"
    else:
        section = ""
    return {"nav": section}
