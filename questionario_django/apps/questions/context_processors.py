def my_questions_badge(request):
    """Selo "Minhas Questoes (N)" no menu: comentarios novos de outros alunos nas questoes
    do usuario. Nao calcula em request HTMX parcial (o menu nao e' redesenhado nelas)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or request.headers.get("HX-Request"):
        return {"my_questions_new_comments": 0}
    from .services import new_comments_on_own_questions

    return {"my_questions_new_comments": new_comments_on_own_questions(user)}
