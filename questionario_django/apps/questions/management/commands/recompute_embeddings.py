"""Recalcula o embedding de todas as perguntas com o modelo configurado em
OLLAMA_EMBED_MODEL. Uso: sempre que o modelo de embedding mudar (dimensao
diferente exige alterar Question.embedding via migration ANTES de rodar isso),
ou se precisar regenerar por qualquer outro motivo.
"""

from django.core.management.base import BaseCommand

from apps.questions.models import Question
from apps.questions.services import get_embedding


class Command(BaseCommand):
    help = "Recalcula o embedding de todas as perguntas com o modelo de embedding atual."

    def handle(self, *args, **options):
        questions = Question.objects.all()
        total = questions.count()
        self.stdout.write(f"Recalculando embedding de {total} pergunta(s)...")

        for i, question in enumerate(questions, start=1):
            question.embedding = get_embedding(question.statement)
            question.save(update_fields=["embedding"])
            self.stdout.write(f"  [{i}/{total}] id={question.id} ok")

        self.stdout.write(self.style.SUCCESS(f"Concluido: {total} pergunta(s) recalculada(s)."))
