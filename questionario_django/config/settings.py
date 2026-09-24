"""
Django settings for the questionario project (Django + Templates + HTMX migration).

See /home/ricardo/.claude/plans/planeje-como-seria-migrar-buzzing-coral.md for the
migration plan this project implements.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-me")

DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

# Atras de um proxy HTTPS (Render): o Django precisa saber que a requisicao original era
# https, senao o CSRF compara a Origin "https://..." com "http://..." e recusa todo POST.
# So' ligar com um proxy de verdade na frente (o cliente poderia forjar o header).
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if env_bool("DJANGO_BEHIND_HTTPS_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --- Semestres: um schema do Postgres por semestre (django-tenants) ---
# SHARED_APPS ficam no schema "public" (contas, sessoes, cache, lista de semestres).
# TENANT_APPS tem uma copia das tabelas em CADA schema de semestre (s2026_1, s2026_2...):
# questoes, respostas, quiz, comentarios, reportes, topicos -- isolamento fisico.
# Ver CLAUDE.md, secao "Semestres (django-tenants)".
SHARED_APPS = [
    "django_tenants",
    "apps.core",
    "apps.accounts",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
TENANT_APPS = [
    "django.contrib.contenttypes",
    "apps.questions",
    "apps.quiz",
    "apps.moderation",
]

# Scripts de analise/importacao (pasta local, fora do git -- ver .gitignore):
# so' registra o app se a pasta existir, pro sistema funcionar igual sem ela.
if (BASE_DIR / "analise").is_dir():
    SHARED_APPS.append("analise")

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]
TENANT_MODEL = "core.Semester"
TENANT_DOMAIN_MODEL = "core.Domain"
DATABASE_ROUTERS = ["django_tenants.routers.TenantSyncRouter"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.SemesterMiddleware",
    "apps.accounts.middleware.RequireRegistrationNumberMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Converte o bloqueio do @ratelimit em RATELIMIT_VIEW (429 "muitas requisicoes");
    # sem ele, o Ratelimited vira um 403 generico.
    "django_ratelimit.middleware.RatelimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.admin_flag",
                "apps.core.context_processors.nav_section",
                "apps.questions.context_processors.my_questions_badge",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database ---------------------------------------------------------------
# Same POSTGRES_* env vars as backend/.env.example; DATABASE_URL is parsed
# manually to avoid adding a dj-database-url dependency for a single URL.

# DATABASE_URL tambem e' aceito: e' o nome que o Render usa na documentacao.
# No Render (que sempre define RENDER=true), sem nenhuma das duas o padrao "localhost"
# so' daria "Connection refused" -- melhor parar com a causa escrita.
if os.environ.get("RENDER") and not (os.environ.get("DJANGO_DATABASE_URL") or os.environ.get("DATABASE_URL")):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "Faltando o endereco do banco: no painel do servico, Environment, adicione DATABASE_URL "
        "com a Internal Database URL do Postgres do Render (ou crie o servico pelo Blueprint)."
    )
DATABASE_URL = (
    os.environ.get("DJANGO_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql://questionario:questionario@localhost:5432/questionario_django"
)


def _parse_database_url(url):
    # postgresql://user:password@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
    }


DATABASES = {"default": _parse_database_url(DATABASE_URL)}

AUTH_USER_MODEL = "accounts.User"

# bcrypt puro (nao passlib) para paridade com backend/app/core/security.py,
# documentado no CLAUDE.md como escolha deliberada.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

LANGUAGE_CODE = "pt-br"
# Fuso da UFPB (Joao Pessoa, UTC-3, sem horario de verao). O banco continua guardando
# em UTC (USE_TZ); isto muda a exibicao e o agrupamento por dia/semana das estatisticas.
TIME_ZONE = "America/Recife"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "questions:create"
LOGOUT_REDIRECT_URL = "accounts:login"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 7 dias, paridade com JWT_EXPIRE_MINUTES=10080 do backend FastAPI

# --- Regras de negocio (valor efetivo mora em AppSettings; estes sao so o seed inicial) ---
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.75"))
QUIZ_SIZE = int(os.environ.get("QUIZ_SIZE", "10"))
REPORT_THRESHOLD = int(os.environ.get("REPORT_THRESHOLD", "3"))

# --- Admin por email (sem coluna role, sem auto-promocao) ---
ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}

# --- Ollama (embeddings) ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
# Build de teste (Render gratuito, 512 MB: o bge-m3 nao cabe). Sem Ollama: embedding
# falso por hash e SEM checagem de questao parecida -- toda questao e' aceita.
EMBEDDINGS_DISABLED = env_bool("EMBEDDINGS_DISABLED")

# --- Google login (opcional/aditivo) ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

# --- E-mail (codigo de confirmacao) ---
# Sem EMAIL_HOST, o e-mail sai no console (so' pra dev). Docker: Mailpit (dev) ou Gmail
# com senha de app (producao), ver .env.example.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Questionario <nao-responda@localhost>")
# Planilha de backup das questoes (uma por semestre, formato do Google Forms original).
# Em Docker, a pasta e' um volume (./planilhas no servidor) -- senao sumiria ao recriar o container.
QUESTION_SHEETS_DIR = os.environ.get("QUESTION_SHEETS_DIR", str(BASE_DIR / "planilhas"))
QUESTION_SHEETS_ASYNC = env_bool("QUESTION_SHEETS_ASYNC", True)

# Envia os e-mails numa thread em background (a tela nao espera o SMTP, ~2 s no Gmail).
# Os testes desligam (conftest) pra ler mail.outbox na hora.
EMAIL_SEND_ASYNC = env_bool("EMAIL_SEND_ASYNC", True)

# --- Cache (usado pelo django-ratelimit) ---
# DatabaseCache (e nao LocMemCache): com varios workers gunicorn, cada processo teria o
# proprio LocMem e o limite "5/min" viraria 5 por worker. O banco e' compartilhado.
# Incremento nao e' atomico (pode passar 1 tentativa a mais em requests simultaneos) --
# aceitavel aqui; Redis seria o ideal se o volume crescer.
# MAX_ENTRIES alto: o padrao do DatabaseCache e' 300 e, ao passar disso, ele apaga 1/3
# das chaves (em ordem de cache_key) -- contadores do rate limit sumiam no meio da janela
# e o limite zerava sem aviso (uma turma gera centenas de chaves: por e-mail/usuario/tela).
# Chaves expiradas continuam sendo limpas no cull.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 100_000},
    }
}

RATELIMIT_VIEW = "apps.core.views.rate_limited"
RATELIMIT_IP_META_KEY = "apps.core.ratelimits.client_ip"
# Quantos proxies confiaveis ficam na frente do Django (nginx, Cloudflare...). 0 = acesso
# direto (usa REMOTE_ADDR). So' aumentar se houver MESMO um proxy -- senao o cliente
# consegue forjar o X-Forwarded-For e fugir do rate limit.
TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))


# Mensagens: "error" vira "danger" (classe .notice--danger do design).
from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: "danger"}
