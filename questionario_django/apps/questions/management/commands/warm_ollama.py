"""Carrega o modelo de embedding no Ollama (1a chamada leva ~12 s) pra nenhum usuario
pagar essa espera ao criar a primeira pergunta. Roda em background no CMD do
Dockerfile; com OLLAMA_KEEP_ALIVE=-1 o modelo fica carregado depois disso. Nunca
falha a subida do servidor: tenta algumas vezes e so' avisa se o Ollama nao responder."""

import time

from django.core.management.base import BaseCommand

from apps.questions import services


class Command(BaseCommand):
    help = "Carrega o modelo de embedding no Ollama (aquecimento)."

    def add_arguments(self, parser):
        parser.add_argument("--attempts", type=int, default=10)
        parser.add_argument("--wait", type=float, default=5.0, help="Segundos entre tentativas.")

    def handle(self, *args, **options):
        for attempt in range(1, options["attempts"] + 1):
            started = time.time()
            try:
                services.get_embedding("aquecimento do modelo de embedding")
            except services.EmbeddingServiceError as exc:
                self.stderr.write(f"warm_ollama: tentativa {attempt} falhou ({exc})")
                time.sleep(options["wait"])
                continue
            self.stdout.write(f"warm_ollama: modelo carregado em {time.time() - started:.1f}s")
            return
        self.stderr.write("warm_ollama: Ollama nao respondeu; o modelo carrega na 1a pergunta criada.")
