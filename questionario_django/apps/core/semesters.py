"""Semestres (django-tenants): qual semestre vale pra cada requisicao, abrir/reativar.

- Aluno: sempre o semestre ATIVO.
- Admin (ADMIN_EMAILS): o semestre SELECIONADO no painel (sessao), padrao o ativo.
O SemesterMiddleware chama pick_semester() e faz connection.set_tenant() -- dai em
diante toda query de questions/quiz/moderation roda no schema daquele semestre.
"""

import re

from django.db import connection, transaction
from django.utils import timezone

ADMIN_SEMESTER_SESSION_KEY = "admin_semester_id"
NAME_RE = re.compile(r"^(\d{4})\.([12])$")


def suggest_next_name(name: str) -> str:
    """Pura. "2026.1" -> "2026.2", "2026.2" -> "2027.1"; fora do padrao -> ""."""
    match = NAME_RE.match(name or "")
    if not match:
        return ""
    year, half = int(match.group(1)), int(match.group(2))
    return f"{year}.2" if half == 1 else f"{year + 1}.1"


def schema_name_for(name: str) -> str:
    """Pura. "2026.1" -> "s2026_1" (nome de schema valido no Postgres)."""
    return "s" + re.sub(r"[^a-z0-9]", "_", name.lower())


def active_semester():
    from .models import Semester

    return Semester.objects.filter(is_active=True).first()


def pick_semester(request):
    from .models import Semester
    from .permissions import is_admin_email

    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and is_admin_email(user.email):
        selected_id = request.session.get(ADMIN_SEMESTER_SESSION_KEY)
        if selected_id:
            selected = Semester.objects.filter(pk=selected_id).first()
            if selected is not None:
                return selected
    return active_semester()


def is_enrolled(user, semester) -> bool:
    from .models import Enrollment

    return Enrollment.objects.filter(user=user, semester=semester).exists()


def enroll(user, semester) -> None:
    from .models import Enrollment

    Enrollment.objects.get_or_create(user=user, semester=semester)


class SemesterError(ValueError):
    """Mensagem vai direto pra tela do admin."""


def open_new_semester(*, name: str, copy_topics: bool, backup_done: bool):
    """Encerra o ativo e abre um novo semestre (schema novo + migrations), copiando as
    configuracoes do anterior e, se pedido, os topicos. Se algo falhar, o schema criado
    e' removido e o ativo continua o mesmo."""
    from django_tenants.utils import schema_context, schema_exists

    from .models import AppSettings, Domain, Semester

    name = (name or "").strip()
    if not backup_done:
        raise SemesterError("Confirme que fez o backup do banco antes de abrir o semestre.")
    if not NAME_RE.match(name):
        raise SemesterError("Use o formato ANO.1 ou ANO.2 (ex: 2026.2).")
    if Semester.objects.filter(name=name).exists():
        raise SemesterError(f"O semestre {name} já existe.")
    schema = schema_name_for(name)
    if schema_exists(schema):
        raise SemesterError(f"Já existe um schema {schema} no banco.")

    connection.set_schema_to_public()
    previous = active_semester()
    base = previous or AppSettings.get_solo()
    topics = []
    if copy_topics and previous is not None:
        with schema_context(previous.schema_name):
            from apps.questions.services import list_topic_names

            topics = list_topic_names()

    # Cria o schema (e roda as migrations nele) FORA da transacao da troca: se isso
    # falhar, TenantMixin.save() ja' apaga o registro e o schema criado.
    semester = Semester(
        name=name,
        schema_name=schema,
        is_active=False,
        similarity_threshold=base.similarity_threshold,
        quiz_size=base.quiz_size,
        report_threshold=base.report_threshold,
    )
    semester.save(verbosity=0)
    try:
        Domain.objects.create(domain=f"{schema}.semestre.local", tenant=semester, is_primary=True)
        if topics:
            with schema_context(schema):
                from apps.questions.models import Topic

                Topic.objects.bulk_create([Topic(name=topic) for topic in topics])
        with transaction.atomic():
            Semester.objects.select_for_update().filter(is_active=True).update(is_active=False, closed_at=timezone.now())
            Semester.objects.filter(pk=semester.pk).update(is_active=True)
    except Exception:
        connection.set_schema_to_public()
        semester.delete(force_drop=True)
        raise
    semester.refresh_from_db()
    return semester


@transaction.atomic
def reactivate(semester) -> None:
    """Desfaz uma abertura por engano: volta a deixar este semestre como o ativo."""
    from .models import Semester

    connection.set_schema_to_public()
    Semester.objects.select_for_update().filter(is_active=True).exclude(pk=semester.pk).update(
        is_active=False, closed_at=timezone.now()
    )
    Semester.objects.filter(pk=semester.pk).update(is_active=True, closed_at=None)
