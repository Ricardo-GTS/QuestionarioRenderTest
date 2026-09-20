from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.core.permissions import admin_required

from .forms import AccountForm, LoginForm, RegisterForm
from .models import User
from .services import verify_google_id_token


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            if User.objects.filter(email__iexact=email).exists():
                form.add_error("email", "Ja existe uma conta com esse e-mail")
            else:
                user = User.objects.create_user(
                    email=email, name=form.cleaned_data["name"], password=form.cleaned_data["password"]
                )
                user.backend = "django.contrib.auth.backends.ModelBackend"
                login(request, user)
                return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form, "google_client_id": settings.GOOGLE_CLIENT_ID})


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["email"].strip().lower(),
                password=form.cleaned_data["password"],
            )
            if user is not None:
                login(request, user)
                return redirect(settings.LOGIN_REDIRECT_URL)
            form.add_error(None, "Credenciais invalidas")
    else:
        form = LoginForm()
    return render(request, "accounts/login.html", {"form": form, "google_client_id": settings.GOOGLE_CLIENT_ID})


@require_POST
def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
@require_POST
def google_login(request):
    credential = request.POST.get("credential", "")
    try:
        payload = verify_google_id_token(credential)
    except Exception:
        messages.error(request, "Falha ao verificar login do Google")
        return redirect("accounts:login")

    google_sub = payload["sub"]
    email = payload["email"].strip().lower()
    name = payload.get("name", email)

    user = User.objects.filter(google_sub=google_sub).first()
    if user is None:
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            user.google_sub = google_sub
            user.save(update_fields=["google_sub"])
        else:
            user = User.objects.create_user(email=email, name=name, password=None, google_sub=google_sub)

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    return redirect(settings.LOGIN_REDIRECT_URL)


@login_required
def account(request):
    user = request.user
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            new_email = form.cleaned_data["email"].strip().lower()
            if new_email != user.email and User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                form.add_error("email", "Ja existe uma conta com esse e-mail")
            else:
                user.name = form.cleaned_data["name"]
                user.email = new_email
                password = form.cleaned_data.get("password")
                if password:
                    user.set_password(password)
                user.save()
                if password:
                    update_session_auth_hash(request, user)
                messages.success(request, "Conta atualizada com sucesso")
                return redirect("accounts:account")
    else:
        form = AccountForm(initial={"name": user.name, "email": user.email})
    return render(request, "accounts/account.html", {"form": form})


@login_required
def delete_account_confirm(request):
    return render(request, "accounts/delete_account_confirm.html")


@login_required
@require_POST
def delete_account(request):
    user = request.user
    logout(request)
    user.delete()
    return redirect("accounts:login")


@login_required
def my_stats(request):
    from apps.moderation.services import compute_user_reputation

    reputation = compute_user_reputation(request.user.id)
    return render(request, "accounts/stats.html", {"reputation": reputation})


@admin_required
def admin_user_list(request):
    from apps.moderation.services import compute_all_users_reputation
    from apps.questions.models import Question

    reputation_map = compute_all_users_reputation()
    question_counts = dict(Question.objects.values_list("author_id").annotate(count=Count("id")))

    users_data = []
    for u in User.objects.all().order_by("name"):
        rep = reputation_map.get(u.id, {"accepted_reports_count": 0, "rejected_reports_count": 0, "questions_removed_count": 0})
        users_data.append(
            {
                "id": u.id,
                "name": u.name,
                "email": u.email,
                "is_admin": u.email.strip().lower() in settings.ADMIN_EMAILS,
                "question_count": question_counts.get(u.id, 0),
                **rep,
            }
        )
    return render(request, "accounts/admin_users.html", {"users": users_data})


@admin_required
@require_POST
def admin_delete_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.pk == request.user.pk:
        if request.headers.get("HX-Request"):
            return HttpResponse("Use a pagina de conta para excluir a propria conta", status=400)
        messages.error(request, "Use a pagina de conta para excluir a propria conta")
        return redirect("accounts:admin_user_list")
    target.delete()
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("accounts:admin_user_list")
