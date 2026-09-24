import math
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.core import ratelimits as rl
from apps.core.permissions import admin_required

from . import services
from .forms import (
    AccountForm,
    EmailCodeForm,
    ForgotPasswordForm,
    LoginForm,
    RegisterForm,
    RegistrationNumberForm,
    ResetPasswordForm,
)
from .models import EmailChangeRequest, PendingRegistration, ReauthRequest, User
from .services import verify_google_id_token


REGISTRATION_NUMBER_TAKEN = "Já existe uma conta com essa matrícula"


def _registration_number_taken(registration_number, exclude_pk=None) -> bool:
    return User.objects.filter(registration_number=registration_number).exclude(pk=exclude_pk).exists()


EMAIL_TAKEN = "Já existe uma conta com esse e-mail"
PENDING_SESSION_KEY = "pending_registration_id"

CODE_ERRORS = {
    "expired": "Código expirado. Peça um novo código.",
    "exhausted": "Muitas tentativas erradas. Peça um novo código.",
}


def _code_error(result) -> str:
    if result.status == "invalid":
        return f"Código incorreto. Restam {result.attempts_left} tentativa(s)."
    return CODE_ERRORS[result.status]


CONFIRM_PAGES = {
    "register": {
        "title": "Confirme seu e-mail",
        "note": "Sua conta só é criada depois da confirmação.",
        "confirm_url": "accounts:confirm_registration",
        "resend_url": "accounts:resend_registration_code",
        "back_url": "accounts:register",
        "back_query": "?editar=1",
        "back_label": "Usar outro e-mail",
    },
    "email_change": {
        "title": "Confirme o novo e-mail",
        "note": "O e-mail da conta só muda depois da confirmação.",
        "confirm_url": "accounts:confirm_email_change",
        "resend_url": "accounts:resend_email_change_code",
        "cancel_url": "accounts:cancel_email_change",
        "cancel_label": "Cancelar troca de e-mail",
    },
    "reauth": {
        "title": "Confirme que é você",
        "note": "Depois de confirmar, você pode alterar o e-mail e a senha da conta por 10 minutos.",
        "confirm_url": "accounts:confirm_reauth",
        "resend_url": "accounts:resend_reauth_code",
        "back_url": "accounts:account",
        "back_query": "",
        "back_label": "Voltar para Minha Conta",
    },
    "password_reset": {
        "title": "Redefinir senha",
        "note": "Se houver uma conta, o código chega em instantes. Digite o código e a nova senha.",
        "confirm_url": "accounts:password_reset_confirm",
        "resend_url": "accounts:password_reset_resend",
        "back_url": "accounts:password_reset_request",
        "back_query": "",
        "back_label": "Usar outro e-mail",
    },
}


def _render_confirm_code(request, *, form, target, mode, timers, destination_text=None):
    """target: e-mail pra onde o codigo foi (mostrado mascarado). Sem target, a tela
    mostra destination_text no lugar (ex: recuperacao de senha pela matricula)."""
    return render(
        request,
        "accounts/confirm_code.html",
        {
            "form": form,
            "email_masked": services.mask_email(target) if target else None,
            "destination_text": destination_text,
            "page": CONFIRM_PAGES[mode],
            "ttl_minutes": services.CODE_TTL_MINUTES,
            **timers,
        },
    )


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key=rl.post_email, rate=rl.PER_TARGET, method="POST", block=True, group="register-email")
def register(request):
    """O User so' e' criado em confirm_registration, depois do codigo enviado por e-mail."""
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            registration_number = form.cleaned_data["registration_number"]
            if User.objects.filter(email__iexact=email).exists():
                form.add_error("email", EMAIL_TAKEN)
            elif _registration_number_taken(registration_number):
                form.add_error("registration_number", REGISTRATION_NUMBER_TAKEN)
            else:
                pending, error = services.start_registration(
                    session_pending_id=request.session.get(PENDING_SESSION_KEY),
                    name=form.cleaned_data["name"],
                    email=email,
                    registration_number=registration_number,
                    password=form.cleaned_data["password"],
                )
                request.session[PENDING_SESSION_KEY] = pending.pk
                if error:
                    messages.error(request, error)
                return redirect("accounts:confirm_registration")
    else:
        initial = {}
        pending = _session_pending(request)
        if pending is not None and request.GET.get("editar"):
            initial = {"name": pending.name, "email": pending.email, "registration_number": pending.registration_number}
        form = RegisterForm(initial=initial)
    return render(request, "accounts/register.html", {"form": form, "google_client_id": settings.GOOGLE_CLIENT_ID})


def _session_pending(request):
    pending_id = request.session.get(PENDING_SESSION_KEY)
    if pending_id is None:
        return None
    return PendingRegistration.objects.filter(pk=pending_id).first()


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
def confirm_registration(request):
    pending = _session_pending(request)
    if pending is None:
        return redirect("accounts:register")
    form = EmailCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = services.complete_registration(pending.pk, form.cleaned_data["code"])
        if result.status == "ok":
            del request.session[PENDING_SESSION_KEY]
            result.user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, result.user)
            messages.success(request, "E-mail confirmado. Sua conta foi criada!")
            return redirect(settings.LOGIN_REDIRECT_URL)
        if result.status in ("missing", "email_taken", "registration_number_taken"):
            request.session.pop(PENDING_SESSION_KEY, None)
            if result.status != "missing":
                messages.error(
                    request,
                    f"{EMAIL_TAKEN if result.status == 'email_taken' else REGISTRATION_NUMBER_TAKEN}. "
                    "Faça o cadastro novamente.",
                )
            return redirect("accounts:register")
        form.add_error("code", _code_error(result))
        pending.refresh_from_db()
    return _render_confirm_code(
        request, form=form, target=pending.email, mode="register", timers=services.code_timers(pending, pending.email)
    )


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@require_POST
def resend_registration_code(request):
    pending = _session_pending(request)
    if pending is None:
        return redirect("accounts:register")
    error = services.resend_registration_code(pending)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, "Enviamos um novo código.")
    return redirect("accounts:confirm_registration")


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key=rl.post_email, rate=rl.PER_TARGET, method="POST", block=True, group="login-email")
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


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
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


REAUTH_SESSION_KEY = "reauth_until"


def _reauth_seconds_left(request) -> int:
    return services.reauth_seconds_left(request.session.get(REAUTH_SESSION_KEY), time.time())


@login_required
def account(request):
    user = request.user
    reauthenticated = _reauth_seconds_left(request) > 0
    initial = {"name": user.name, "email": user.email}
    if request.method == "POST":
        form = AccountForm(request.POST, initial=initial, reauthenticated=reauthenticated)
        if form.is_valid():
            new_email = form.cleaned_data["email"].strip().lower()
            email_changed = new_email != user.email
            if email_changed and User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
                form.add_error("email", EMAIL_TAKEN)
            else:
                user.name = form.cleaned_data["name"]
                password = form.cleaned_data.get("password")
                if password:
                    user.set_password(password)
                user.save()
                if password:
                    # Mantem esta sessao; as outras sessoes da conta caem (hash de sessao muda).
                    update_session_auth_hash(request, user)
                    transaction.on_commit(lambda: services.send_password_changed_notice(user.email))
                if not email_changed:
                    messages.success(request, "Conta atualizada com sucesso")
                    return redirect("accounts:account")
                # user.email so' muda depois do codigo enviado ao novo e-mail.
                _, error = services.start_email_change(user, new_email)
                if error:
                    messages.error(request, error)
                return redirect("accounts:confirm_email_change")
    else:
        form = AccountForm(initial=initial, reauthenticated=reauthenticated)
    pending_change = EmailChangeRequest.objects.filter(user=user).first()
    return render(
        request,
        "accounts/account.html",
        {
            "form": form,
            "reauthenticated": reauthenticated,
            "reauth_minutes_left": math.ceil(_reauth_seconds_left(request) / 60),
            "email_masked": services.mask_email(user.email),
            "pending_change_email": services.mask_email(pending_change.new_email) if pending_change else None,
        },
    )


@login_required
@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key="user", rate=rl.PER_TARGET, method="POST", block=True, group="reauth-send")
@require_POST
def reauth_start(request):
    error = services.start_reauth(request.user)
    if error:
        messages.error(request, error)
    return redirect("accounts:confirm_reauth")


@login_required
@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key="user", rate=rl.CODE_CONFIRM_PER_USER, method="POST", block=True, group="reauth-confirm")
def confirm_reauth(request):
    if not ReauthRequest.objects.filter(user=request.user).exists():
        return redirect("accounts:account")
    form = EmailCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = services.complete_reauth(request.user, form.cleaned_data["code"])
        if result.status == "ok":
            request.session[REAUTH_SESSION_KEY] = time.time() + services.REAUTH_MINUTES * 60
            messages.success(
                request, f"Confirmado. Você pode alterar e-mail e senha pelos próximos {services.REAUTH_MINUTES} minutos."
            )
            return redirect("accounts:account")
        if result.status == "missing":
            return redirect("accounts:account")
        form.add_error("code", _code_error(result))
    return _render_confirm_code(
        request,
        form=form,
        target=request.user.email,
        mode="reauth",
        timers=services.reauth_timers(request.user),
    )


@login_required
@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key="user", rate=rl.PER_TARGET, method="POST", block=True, group="reauth-send")
@require_POST
def resend_reauth_code(request):
    error = services.start_reauth(request.user)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, "Enviamos um novo código.")
    return redirect("accounts:confirm_reauth")


@login_required
@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key="user", rate=rl.CODE_CONFIRM_PER_USER, method="POST", block=True, group="email-change-confirm")
def confirm_email_change(request):
    req = EmailChangeRequest.objects.filter(user=request.user).first()
    if req is None:
        return redirect("accounts:account")
    form = EmailCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = services.complete_email_change(request.user, form.cleaned_data["code"])
        if result.status == "ok":
            messages.success(request, f"E-mail alterado para {result.user.email}.")
            return redirect("accounts:account")
        if result.status in ("missing", "email_taken"):
            if result.status == "email_taken":
                messages.error(request, f"{EMAIL_TAKEN}. A troca foi cancelada.")
            return redirect("accounts:account")
        form.add_error("code", _code_error(result))
        req.refresh_from_db()
    return _render_confirm_code(
        request, form=form, target=req.new_email, mode="email_change", timers=services.code_timers(req, req.new_email)
    )


@login_required
@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key="user", rate=rl.PER_TARGET, method="POST", block=True, group="email-change-send")
@require_POST
def resend_email_change_code(request):
    req = EmailChangeRequest.objects.filter(user=request.user).first()
    if req is None:
        return redirect("accounts:account")
    error = services.resend_email_change_code(req)
    if error:
        messages.error(request, error)
    else:
        messages.success(request, "Enviamos um novo código.")
    return redirect("accounts:confirm_email_change")


@login_required
@require_POST
def cancel_email_change(request):
    EmailChangeRequest.objects.filter(user=request.user).delete()
    messages.success(request, "Troca de e-mail cancelada.")
    return redirect("accounts:account")


RESET_SESSION_KEY = "password_reset_identifier"
RESET_CODE_ERROR = (
    "Código incorreto ou expirado. Confira o código mais recente ou peça um novo "
    "(depois de 5 tentativas erradas, o código deixa de valer)."
)


def _session_reset_identifier(request):
    identifier = request.session.get(RESET_SESSION_KEY)
    return tuple(identifier) if identifier else None


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@ratelimit(key=rl.post_identifier, rate=rl.PER_TARGET, method="POST", block=True, group="reset-identifier")
def password_reset_request(request):
    form = ForgotPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        identifier = form.cleaned_data["identifier"]
        services.start_password_reset(identifier)
        request.session[RESET_SESSION_KEY] = list(identifier)
        return redirect("accounts:password_reset_confirm")
    return render(request, "accounts/password_reset_request.html", {"form": form})


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
def password_reset_confirm(request):
    """Mesma tela e mesmas mensagens com ou sem conta (nao revela quais existem)."""
    identifier = _session_reset_identifier(request)
    if identifier is None:
        return redirect("accounts:password_reset_request")
    form = ResetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = services.complete_password_reset(
            identifier, form.cleaned_data["code"], form.cleaned_data["new_password"]
        )
        if result.status == "ok":
            del request.session[RESET_SESSION_KEY]
            result.user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, result.user)
            messages.success(request, "Senha alterada. Você já está conectado.")
            return redirect(settings.LOGIN_REDIRECT_URL)
        # Mensagem unica (sem "restam N tentativas"): a contagem so' andaria se a conta existisse.
        form.add_error("code", RESET_CODE_ERROR)
    kind, value = identifier
    # Pela matricula, NAO mostra o e-mail mascarado: entregaria que a matricula existe e
    # daria uma pista do e-mail de outra pessoa.
    return _render_confirm_code(
        request,
        form=form,
        target=value if kind == "email" else None,
        destination_text="o e-mail cadastrado nessa matrícula" if kind == "registration_number" else None,
        mode="password_reset",
        timers=services.password_reset_timers(identifier),
    )


@ratelimit(key="ip", rate=rl.IP_CEILING, method="POST", block=True, group="auth-ip")
@require_POST
def password_reset_resend(request):
    identifier = _session_reset_identifier(request)
    if identifier is None:
        return redirect("accounts:password_reset_request")
    services.resend_password_reset_code(identifier)
    messages.success(request, "Se houver uma conta, enviamos um novo código.")
    return redirect("accounts:password_reset_confirm")


@login_required
def complete_registration_number(request):
    """1o acesso de conta sem matricula (login com Google ou conta antiga) -- o
    RequireRegistrationNumberMiddleware manda pra ca ate a matricula ser preenchida."""
    user = request.user
    if user.registration_number:
        return redirect(settings.LOGIN_REDIRECT_URL)
    if request.method == "POST":
        form = RegistrationNumberForm(request.POST)
        if form.is_valid():
            registration_number = form.cleaned_data["registration_number"]
            if _registration_number_taken(registration_number, exclude_pk=user.pk):
                form.add_error("registration_number", REGISTRATION_NUMBER_TAKEN)
            else:
                user.registration_number = registration_number
                user.save(update_fields=["registration_number"])
                return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = RegistrationNumberForm()
    return render(request, "accounts/complete_registration_number.html", {"form": form})


@login_required
def my_interactions(request):
    """Aba "Minhas interacoes": questoes em que o aluno comentou (com selo de comentarios
    novos; o painel de comentarios abre ali mesmo) e os reportes de questoes que ele fez."""
    from apps.moderation.models import Report
    from apps.questions.services import commented_questions_for

    return render(
        request,
        "accounts/interactions.html",
        {
            "questions": commented_questions_for(request.user),
            "reports": Report.objects.filter(reporter=request.user).select_related("question").order_by("-created_at"),
        },
    )


@login_required
def my_stats(request):
    from .stats import build_user_stats

    return render(request, "accounts/stats.html", {"stats": build_user_stats(request.user)})


@admin_required
def admin_user_list(request):
    from apps.moderation.services import compute_all_users_reputation
    from apps.questions.models import Question

    reputation_map = compute_all_users_reputation()
    question_counts = dict(Question.objects.values_list("author_id").annotate(count=Count("id")))

    # So' quem participa do semestre que o admin esta vendo (contas sao compartilhadas;
    # reputacao e contagens ja' vem do schema desse semestre).
    users = User.objects.filter(enrollments__semester=request.semester).order_by("name")
    users_data = [_admin_user_data(u, reputation_map, question_counts) for u in users]
    return render(request, "accounts/admin_users.html", {"users": users_data})


def _admin_user_data(u, reputation_map, question_counts):
    rep = reputation_map.get(u.id, {"accepted_reports_count": 0, "rejected_reports_count": 0, "questions_removed_count": 0})
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "registration_number": u.registration_number,
        "is_admin": u.email.strip().lower() in settings.ADMIN_EMAILS,
        "question_count": question_counts.get(u.id, 0),
        **rep,
    }


@admin_required
@require_POST
def admin_update_registration_number(request, user_id):
    """Depois de preenchida, a matricula so' e' alterada por aqui (admin)."""
    from apps.moderation.services import compute_user_reputation
    from apps.questions.models import Question

    target = get_object_or_404(User, pk=user_id)
    form = RegistrationNumberForm(request.POST)
    error = None
    if form.is_valid():
        registration_number = form.cleaned_data["registration_number"]
        if _registration_number_taken(registration_number, exclude_pk=target.pk):
            error = REGISTRATION_NUMBER_TAKEN
        else:
            target.registration_number = registration_number
            target.save(update_fields=["registration_number"])
    else:
        error = form.errors["registration_number"][0]
    if not request.headers.get("HX-Request"):
        if error:
            messages.error(request, error)
        return redirect("accounts:admin_user_list")
    user_data = _admin_user_data(
        target,
        {target.id: compute_user_reputation(target.id)},
        {target.id: Question.objects.filter(author=target).count()},
    )
    return render(request, "accounts/_admin_user_card.html", {"u": user_data, "error": error})


@admin_required
@require_POST
def admin_delete_user(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.pk == request.user.pk:
        if request.headers.get("HX-Request"):
            return HttpResponse("Não é possível excluir a própria conta", status=400)
        messages.error(request, "Não é possível excluir a própria conta")
        return redirect("accounts:admin_user_list")
    from .services import delete_user_everywhere

    delete_user_everywhere(target)
    if request.headers.get("HX-Request"):
        return HttpResponse("")
    return redirect("accounts:admin_user_list")


@login_required
def join_semester(request):
    """Conta de um semestre anterior entrando depois que um novo foi aberto."""
    from apps.core.semesters import enroll, is_enrolled

    semester = getattr(request, "semester", None)
    if semester is None or is_enrolled(request.user, semester):
        return redirect(settings.LOGIN_REDIRECT_URL)
    if request.method == "POST":
        enroll(request.user, semester)
        messages.success(request, f"Bem-vindo ao semestre {semester.name}!")
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "accounts/join_semester.html", {"semester": semester})


@login_required
def profile(request):
    """Aba "Perfil" da barra de baixo (celular): reune o que no computador fica na barra
    do topo e no menu da conta -- Interacoes, Estatisticas, Conta, Admin e Sair."""
    return render(request, "accounts/profile.html")
