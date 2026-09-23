from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


REGISTRATION_NUMBER_VALIDATOR = RegexValidator(
    r"^\d{8,12}$", "A matrícula deve ter apenas números, entre 8 e 12 dígitos."
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError("Email e obrigatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Conta so-Google -- equivalente a hashed_password=None no schema atual.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        # Superuser Django -- credencial SEPARADA de "email em ADMIN_EMAILS" (admin
        # da aplicacao). So usada para acessar /django-admin/, nunca para a app em si.
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    # null=True so' pra contas antigas e contas criadas via Google: essas sao obrigadas
    # a preencher no 1o acesso (accounts.middleware.RequireRegistrationNumberMiddleware).
    registration_number = models.CharField(
        max_length=12, unique=True, null=True, blank=True, validators=[REGISTRATION_NUMBER_VALIDATOR]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    def __str__(self):
        return self.email



class EmailCodeBase(models.Model):
    """Codigo de confirmacao enviado por e-mail (so' o hash e' guardado). Regras de
    validade/tentativas em accounts.services (issue_code/check); cooldown e limite de
    envio sao por e-mail de destino, via EmailSendLog."""

    code_hash = models.CharField(max_length=64, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    code_expires_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class PendingRegistration(EmailCodeBase):
    """Cadastro aguardando o codigo: o User so' e' criado quando o codigo e' confirmado.
    Amarrado a sessao do navegador que o criou (request.session), NAO ao e-mail -- de
    proposito: se fosse um por e-mail, outra pessoa poderia se cadastrar com o mesmo
    e-mail e sobrescrever a senha do pendente da vitima antes dela digitar o codigo.
    Nao reserva e-mail nem matricula (unicidade e' checada de novo ao confirmar)."""

    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=120)
    registration_number = models.CharField(max_length=12)
    password_hash = models.CharField(max_length=128)

    def __str__(self):
        return self.email


class EmailChangeRequest(EmailCodeBase):
    """Troca de e-mail aguardando o codigo enviado ao novo e-mail -- user.email so'
    muda quando o codigo e' confirmado."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="email_change_request")
    new_email = models.EmailField()

    def __str__(self):
        return f"{self.user.email} -> {self.new_email}"


class PasswordResetRequest(EmailCodeBase):
    """Pedido de redefinicao de senha ("Esqueci minha senha") -- um por usuario; pedir
    de novo gera um codigo novo e invalida o anterior."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="password_reset_request")

    def __str__(self):
        return self.user.email


class ReauthRequest(EmailCodeBase):
    """Codigo enviado ao e-mail ATUAL pra liberar a troca de e-mail/senha na pagina Conta
    por REAUTH_MINUTES (confirma que e' o dono da conta, nao so' alguem com a sessao aberta)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="reauth_request")

    def __str__(self):
        return self.user.email


class EmailSendLog(models.Model):
    """Um registro por codigo enviado -- base do cooldown e do limite por hora POR
    E-MAIL de destino (vale entre sessoes/usuarios, protege a caixa de terceiros e a
    cota do SMTP)."""

    email = models.EmailField()
    sent_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=["email", "sent_at"], name="ix_email_send_log_email_sent")]
