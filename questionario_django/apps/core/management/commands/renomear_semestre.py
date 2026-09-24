"""Renomeia um semestre (nome, schema, dominio e planilha, juntos).

    python manage.py renomear_semestre 2026.1 2025.2 --dry-run
    python manage.py renomear_semestre 2026.1 2025.2

Fazer backup antes (scripts/backup_db.sh). Backups antigos continuam com o nome/schema
de antes -- restaurar um deles traz o semestre com o nome antigo.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Renomeia um semestre (nome, schema do Postgres, dominio e planilha)."

    def add_arguments(self, parser):
        parser.add_argument("old", help='Nome atual, ex: "2026.1"')
        parser.add_argument("new", help='Nome novo, ex: "2025.2"')
        parser.add_argument("--dry-run", action="store_true", help="So' mostra o que seria feito.")

    def handle(self, *args, old, new, dry_run, **options):
        from apps.core.models import Semester
        from apps.core.semesters import SemesterError, rename_semester, schema_name_for
        from apps.questions.sheets import sheet_filename

        connection.set_schema_to_public()
        semester = Semester.objects.filter(name=old).first()
        if semester is None:
            raise CommandError(f"Semestre {old} nao existe.")
        self.stdout.write(f"Semestre: {old} -> {new}{' (ativo)' if semester.is_active else ''}")
        self.stdout.write(f"Schema:   {semester.schema_name} -> {schema_name_for(new)}")
        self.stdout.write(f"Planilha: {sheet_filename(old)} -> {sheet_filename(new)}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: nada foi alterado."))
            return
        try:
            rename_semester(semester, new)
        except SemesterError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Pronto: semestre {old} agora e' {new}."))
