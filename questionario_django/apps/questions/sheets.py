"""Planilha de backup das questoes (mesmo formato das respostas do Google Forms original),
uma por semestre em QUESTION_SHEETS_DIR, e planilha por periodo gerada na hora.

A planilha do semestre e' SEMPRE regenerada inteira a partir do banco (nao editada linha
a linha): nunca desalinha, pega mudancas em massa (.update() de topico) e se conserta
sozinha na proxima mudanca se uma gravacao falhar. O banco e' a fonte principal.

Gravacao: trava de arquivo (fcntl.flock) entre os workers do gunicorn + escrita num
temporario e os.replace atomico -- uma queda no meio nunca deixa a planilha corrompida.
Agendamento: depois do commit, numa thread (EMAIL_SEND_ASYNC-like: QUESTION_SHEETS_ASYNC),
agrupando mudancas seguidas do mesmo semestre.
"""

import fcntl
import logging
import os
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.db import connection, connections, transaction
from django.utils import timezone
from openpyxl import Workbook

logger = logging.getLogger(__name__)

SHEET_TITLE = "Form Responses 1"  # mesma aba do Google Forms original
COLUMNS = [
    "Timestamp",
    "Email Address",
    "Nome Completo",
    "Tópico da questão",
    "Questão",
    "Resposta",
    "Citações e referências",
    "Pertinência",
    "Situação",
]
STATUS_LABELS = {"active": "Ativa", "reported": "Em análise", "removed": "Removida"}


# --- Regras puras ---


def question_row(question) -> list:
    """Uma linha da planilha. Timestamp no fuso local, sem tzinfo (o openpyxl nao grava
    datetime com fuso), como no original."""
    return [
        timezone.localtime(question.created_at).replace(tzinfo=None),
        question.author.email,
        question.author.name,
        question.topic,
        question.statement,
        "Verdadeira" if question.correct_answer else "Falsa",
        question.citations_references,
        question.pertinence,
        STATUS_LABELS.get(question.status, question.status),
    ]


def sheet_filename(semester_name: str) -> str:
    return f"Banco_de_Questoes_{semester_name}.xlsx"


def range_filename(start: date, end: date) -> str:
    return f"Banco_de_Questoes_{start.isoformat()}_a_{end.isoformat()}.xlsx"


def parse_range(start_value: str, end_value: str, available):
    """Pura. Datas do formulario (AAAA-MM-DD) -> ((inicio, fim_exclusivo) com fuso local, None)
    ou (None, mensagem de erro). O ultimo dia entra inteiro (ate' 23h59 locais)."""
    if available is None:
        return None, "Ainda não há questões para exportar."
    try:
        start = date.fromisoformat(start_value or "")
        end = date.fromisoformat(end_value or "")
    except ValueError:
        return None, "Informe datas válidas."
    first, last = available
    if start > end:
        return None, "A data de início é depois da data de fim."
    if start < first or end > last:
        return None, f"Escolha datas entre {first:%d/%m/%Y} e {last:%d/%m/%Y}."
    tz = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(start, time.min), tz),
        timezone.make_aware(datetime.combine(end + timedelta(days=1), time.min), tz),
    ), None


def build_workbook(rows, columns=COLUMNS) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET_TITLE
    sheet.append(columns)
    for row in rows:
        sheet.append(row)
    return workbook


# --- Planilha do semestre (arquivo em disco) ---


def sheet_path(semester) -> Path:
    return Path(settings.QUESTION_SHEETS_DIR) / sheet_filename(semester.name)


def _questions():
    from .models import Question

    return Question.objects.select_related("author").order_by("created_at", "id")


def write_sheet(semester) -> Path:
    """Regenera a planilha do semestre a partir do banco (trava + troca atomica)."""
    from django_tenants.utils import schema_context

    path = sheet_path(semester)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(path.with_name(f".{path.name}.lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)  # um gravador por vez, entre processos
        try:
            # Le o banco DENTRO da trava: o ultimo a gravar sempre grava o estado mais novo.
            with schema_context(semester.schema_name):
                rows = [question_row(q) for q in _questions()]
            build_workbook(rows).save(tmp)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
    return path


_state_lock = threading.Lock()
_running: set[int] = set()
_dirty: set[int] = set()


def schedule_sheet_update(semester=None) -> None:
    """Agenda a regeneracao da planilha do semestre (padrao: o da conexao) depois do commit."""
    from apps.core.semesters import connection_semester

    if semester is None:
        semester = connection_semester()  # funciona tambem dentro de schema_context()
    if semester is None:
        return
    semester_id = semester.pk
    transaction.on_commit(lambda: _kick(semester_id))


def _kick(semester_id: int) -> None:
    if not settings.QUESTION_SHEETS_ASYNC:
        _write_safely(semester_id)
        return
    with _state_lock:
        if semester_id in _running:
            _dirty.add(semester_id)  # ja' esta gravando: roda mais uma vez no fim
            return
        _running.add(semester_id)
    threading.Thread(target=_worker, args=(semester_id,), daemon=True).start()


def _worker(semester_id: int) -> None:
    try:
        while True:
            _write_safely(semester_id)
            with _state_lock:
                if semester_id in _dirty:
                    _dirty.discard(semester_id)
                    continue
                _running.discard(semester_id)
                return
    finally:
        with _state_lock:
            _running.discard(semester_id)
        connections.close_all()  # thread com conexao propria


def _write_safely(semester_id: int) -> None:
    """Nunca deixa a falha da planilha subir: a questao ja' esta salva no banco."""
    from apps.core.models import Semester

    try:
        write_sheet(Semester.objects.get(pk=semester_id))
    except Exception:
        logger.exception("Falha ao gravar a planilha de backup do semestre %s", semester_id)


# --- Planilha por periodo (gerada na hora, nao salva) ---


def available_range():
    """(primeira data, ultima data) das questoes somando TODOS os semestres, ou None.
    Nao usa a data de abertura do semestre: questoes importadas tem a data original do
    formulario, anterior a abertura."""
    from django.db.models import Max, Min
    from django_tenants.utils import schema_context

    from apps.core.models import Semester

    firsts, lasts = [], []
    for semester in Semester.objects.all():
        with schema_context(semester.schema_name):
            from .models import Question

            agg = Question.objects.aggregate(first=Min("created_at"), last=Max("created_at"))
        if agg["first"]:
            firsts.append(agg["first"])
            lasts.append(agg["last"])
    if not firsts:
        return None
    return timezone.localtime(min(firsts)).date(), timezone.localtime(max(lasts)).date()


def build_range_workbook(start_dt, end_dt):
    """Questoes criadas em [start_dt, end_dt) em todos os semestres, com a coluna Semestre.
    Devolve (workbook, quantidade)."""
    from django_tenants.utils import schema_context

    from apps.core.models import Semester

    collected = []
    for semester in Semester.objects.all():
        with schema_context(semester.schema_name):
            for question in _questions().filter(created_at__gte=start_dt, created_at__lt=end_dt):
                collected.append((question.created_at, question.id, question_row(question) + [semester.name]))
    collected.sort(key=lambda item: (item[0], item[1]))
    return build_workbook([row for _, _, row in collected], COLUMNS + ["Semestre"]), len(collected)


def rename_sheet_file(old_name: str, semester) -> None:
    """Depois de renomear o semestre: o arquivo (e a trava) do nome antigo passam a ter o
    nome novo, e a planilha e' regenerada (o banco confirma o conteudo). Se o antigo nao
    existir, so' gera. Nunca deixa a falha subir -- o semestre ja' foi renomeado."""
    directory = Path(settings.QUESTION_SHEETS_DIR)
    old_path = directory / sheet_filename(old_name)
    new_path = sheet_path(semester)
    try:
        if old_path.exists():
            directory.mkdir(parents=True, exist_ok=True)
            with open(new_path.with_name(f".{new_path.name}.lock"), "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                os.replace(old_path, new_path)
            old_lock = old_path.with_name(f".{old_path.name}.lock")
            if old_lock.exists():
                old_lock.unlink()
    except OSError:
        logger.exception("Falha ao renomear a planilha %s para %s", old_path.name, new_path.name)
    # Na hora, sem thread: renomear e' raro, e pelo comando (manage.py renomear_semestre) o
    # processo termina antes de uma thread em segundo plano rodar.
    _write_safely(semester.pk)
