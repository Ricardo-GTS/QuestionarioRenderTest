"""Comando criar_primeiro_semestre: move o layout antigo (tabelas das apps por semestre
num schema so') para o schema do primeiro semestre, sem perder linha."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django_tenants.utils import schema_context, schema_exists

from apps.accounts.models import User
from apps.core.models import Enrollment, Semester
from apps.questions.models import Question, QuestionComment
from conftest import _fake_get_embedding


def _table_exists(schema, table):
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", [f'"{schema}"."{table}"'])
        return cursor.fetchone()[0] is not None


@pytest.fixture
def legacy_layout():
    """Schema "legacy" com as tabelas e dados das apps por semestre, e NENHUM Semester
    cadastrado -- como o banco real antes da migracao (la' o schema e' o public)."""
    connection.set_schema_to_public()
    legacy = Semester(name="legado", schema_name="legacy", similarity_threshold=0.8, quiz_size=10, report_threshold=3)
    legacy.save(verbosity=0)
    author = User.objects.create_user(email="autor@example.com", name="Autor", password="x" * 8, registration_number="10000001")
    User.objects.create_user(email="admin@example.com", name="Admin", password="x" * 8, registration_number="10000009")
    with schema_context("legacy"):
        q = Question.objects.create(
            author=author, statement="Questao antiga", correct_answer=True, topic="Geral",
            citations_references="r", pertinence="p", embedding=_fake_get_embedding("antiga"),
        )
        QuestionComment.objects.create(question=q, author=author, text="comentario antigo")
    connection.set_schema_to_public()
    for semester in Semester.objects.all():
        semester.delete()  # auto_drop_schema=False: o schema (e os dados) ficam
    assert schema_exists("legacy")
    return author


@pytest.mark.django_db
def test_dry_run_changes_nothing(legacy_layout):
    out = StringIO()
    call_command("criar_primeiro_semestre", "2025.2", source_schema="legacy", dry_run=True, stdout=out)
    assert "mover legacy.questions_question (1 linhas)" in out.getvalue()
    assert "Vincular 1 usuarios" in out.getvalue()  # o admin fica de fora
    assert not Semester.objects.exists()
    assert not schema_exists("s2025_2")


@pytest.mark.django_db
def test_moves_tables_keeps_rows_and_works_after(legacy_layout):
    author = legacy_layout
    call_command("criar_primeiro_semestre", "2025.2", source_schema="legacy", stdout=StringIO())
    semester = Semester.objects.get()
    assert semester.name == "2025.2" and semester.is_active and semester.schema_name == "s2025_2"
    assert not _table_exists("legacy", "questions_question")  # movida, nao copiada
    with schema_context("s2025_2"):
        assert Question.objects.get().statement == "Questao antiga"
        assert QuestionComment.objects.get().text == "comentario antigo"
        # migrations marcadas + a sequencia de ids nova nao colide com as antigas
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM django_migrations WHERE app = 'questions'")
            assert cursor.fetchone()[0] > 0
            cursor.execute("INSERT INTO django_migrations (app, name, applied) VALUES ('x', 'y', now())")
        # criar dado novo depois funciona (identity das tabelas movidas)
        Question.objects.create(
            author=author, statement="Nova", correct_answer=False, topic="Geral",
            citations_references="r", pertinence="p", embedding=_fake_get_embedding("nova"),
        )
        assert Question.objects.count() == 2
    connection.set_schema_to_public()
    call_command("migrate_schemas", tenant=True, schema_name="s2025_2", interactive=False, verbosity=0)  # idempotente
    assert list(Enrollment.objects.values_list("user__email", flat=True)) == ["autor@example.com"]


@pytest.mark.django_db
def test_refuses_when_semester_exists_or_bad_name(legacy_layout):
    with pytest.raises(CommandError):
        call_command("criar_primeiro_semestre", "primeiro", source_schema="legacy", stdout=StringIO())
    call_command("criar_primeiro_semestre", "2025.2", source_schema="legacy", stdout=StringIO())
    with pytest.raises(CommandError):
        call_command("criar_primeiro_semestre", "2026.1", source_schema="legacy", stdout=StringIO())
