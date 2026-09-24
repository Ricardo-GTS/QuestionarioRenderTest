"""Gera (regenera) a planilha de backup das questoes a partir do banco.

    python manage.py gerar_planilha --semestre 2026.1
    python manage.py gerar_planilha            # todos os semestres
"""

import time

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Gera a planilha de backup das questoes de um semestre (ou de todos)."

    def add_arguments(self, parser):
        parser.add_argument("--semestre", help='Nome do semestre, ex: "2026.1". Sem ele, todos.')

    def handle(self, *args, semestre=None, **options):
        from apps.core.models import Semester
        from apps.questions.sheets import write_sheet

        semesters = Semester.objects.all()
        if semestre:
            semesters = semesters.filter(name=semestre)
            if not semesters.exists():
                raise CommandError(f"Semestre {semestre} nao existe.")
        for semester in semesters:
            started = time.time()
            path = write_sheet(semester)
            self.stdout.write(f"{semester.name}: {path} ({time.time() - started:.1f}s)")
