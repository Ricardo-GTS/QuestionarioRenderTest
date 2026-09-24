from datetime import date

import httpx
from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .permissions import admin_required


def health(request):
    checks = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        response = httpx.get(settings.OLLAMA_HOST, timeout=5.0)
        checks["ollama"] = "ok" if response.status_code < 500 else "degraded"
    except Exception:
        checks["ollama"] = "error"

    status = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    return JsonResponse({"status": status, "checks": checks})


def rate_limited(request, exception=None):
    return HttpResponse("Muitas requisicoes -- tente novamente em instantes.", status=429)


# --- Semestres (painel do admin) ---


def _semesters_overview():
    """Lista com contagens; questoes vem do schema de cada semestre (poucos semestres)."""
    from django.db.models import Count
    from django_tenants.utils import schema_context

    from .models import Semester

    rows = []
    for semester in Semester.objects.annotate(students=Count("enrollments")):
        with schema_context(semester.schema_name):
            from apps.questions.models import Question

            questions = Question.objects.count()
        rows.append({"semester": semester, "students": semester.students, "questions": questions})
    return rows


@admin_required
def semesters(request, error=None, range_values=None):
    from apps.questions.sheets import available_range

    from .semesters import active_semester, suggest_next_name

    active = active_semester()
    available = available_range()
    return render(
        request,
        "core/semesters.html",
        {
            "rows": _semesters_overview(),
            "active": active,
            "suggested_name": suggest_next_name(active.name) if active else "",
            "error": error,
            "available": available,
            "range_values": range_values
            or ({"start": available[0].isoformat(), "end": available[1].isoformat()} if available else {}),
        },
    )


@admin_required
@require_POST
def open_semester(request):
    from .semesters import ADMIN_SEMESTER_SESSION_KEY, SemesterError, open_new_semester

    try:
        semester = open_new_semester(
            name=request.POST.get("name", ""),
            copy_topics=bool(request.POST.get("copy_topics")),
            backup_done=bool(request.POST.get("backup_done")),
        )
    except SemesterError as exc:
        return semesters(request, error=str(exc))
    request.session.pop(ADMIN_SEMESTER_SESSION_KEY, None)
    messages.success(request, f"Semestre {semester.name} aberto. O anterior foi encerrado e continua disponível para consulta.")
    return redirect("core:semesters")


@admin_required
@require_POST
def reactivate_semester(request, semester_id):
    from .models import Semester
    from .semesters import ADMIN_SEMESTER_SESSION_KEY, reactivate

    semester = get_object_or_404(Semester, pk=semester_id)
    reactivate(semester)
    request.session.pop(ADMIN_SEMESTER_SESSION_KEY, None)
    messages.success(request, f"Semestre {semester.name} voltou a ser o ativo.")
    return redirect("core:semesters")


@admin_required
@require_POST
def select_semester(request):
    """So' muda o que o ADMIN esta vendo (sessao dele); o semestre ativo nao muda."""
    from .models import Semester
    from .semesters import ADMIN_SEMESTER_SESSION_KEY

    semester = get_object_or_404(Semester, pk=request.POST.get("semester"))
    if semester.is_active:
        request.session.pop(ADMIN_SEMESTER_SESSION_KEY, None)
    else:
        request.session[ADMIN_SEMESTER_SESSION_KEY] = semester.pk
    next_url = request.POST.get("next", "")
    # So' volta pra uma URL do proprio sistema (evita open redirect via "next").
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = "moderation:dashboard"
    return redirect(next_url)


# --- Planilhas de backup das questoes ---


@admin_required
def download_sheet(request, semester_id):
    from django.http import FileResponse

    from apps.questions.sheets import sheet_filename, sheet_path, write_sheet

    from .models import Semester

    semester = get_object_or_404(Semester, pk=semester_id)
    path = sheet_path(semester)
    if not path.exists():
        write_sheet(semester)  # primeira vez: gera na hora
    return FileResponse(open(path, "rb"), as_attachment=True, filename=sheet_filename(semester.name))


@admin_required
@require_POST
def regenerate_sheet(request, semester_id):
    from apps.questions.sheets import write_sheet

    from .models import Semester

    semester = get_object_or_404(Semester, pk=semester_id)
    write_sheet(semester)
    messages.success(request, f"Planilha do semestre {semester.name} regenerada a partir do banco.")
    return redirect("core:semesters")


@admin_required
@require_POST
def export_range(request):
    """Planilha de um periodo (todos os semestres), gerada na hora e so' baixada."""
    from io import BytesIO

    from apps.questions.sheets import available_range, build_range_workbook, parse_range, range_filename

    start, end = request.POST.get("start", ""), request.POST.get("end", "")
    interval, error = parse_range(start, end, available_range())
    if error:
        return semesters(request, error=error, range_values={"start": start, "end": end})
    workbook, count = build_range_workbook(*interval)
    if count == 0:
        return semesters(request, error="Nenhuma questão nesse período.", range_values={"start": start, "end": end})
    buffer = BytesIO()
    workbook.save(buffer)
    response = HttpResponse(
        buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    first_day, last_day = date.fromisoformat(start), date.fromisoformat(end)
    response["Content-Disposition"] = f'attachment; filename="{range_filename(first_day, last_day)}"'
    return response
