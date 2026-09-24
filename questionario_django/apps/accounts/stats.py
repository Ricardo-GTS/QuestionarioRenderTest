"""Estatisticas do aluno (pagina /estatisticas).

Funcoes puras em cima (sequencia de dias, serie semanal, porcentagens com minimo,
precisao dos reportes, divisao de topicos); consultas agregadas embaixo -- cada secao e'
um values().annotate()/aggregate(), nunca um laco por questao, entao o numero de queries
da pagina nao cresce com o volume de dados. Dia/semana seguem o fuso local (TIME_ZONE).
"""

from datetime import timedelta

from django.db.models import Count, Min, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

MIN_ANSWERS = 5  # porcentagem por topico/questao so' com 5+ respostas
MIN_CLASS_ANSWERS = 20  # media da turma so' com 20+ respostas no sistema (anonimato)
WEEKS = 8
TOP_TOPICS = 3


# --- Regras puras ---


def percent(correct: int, total: int, minimum: int = MIN_ANSWERS):
    if total == 0 or total < minimum:
        return None
    return round(100 * correct / total)


def streak(days: set, today) -> tuple[int, int]:
    """(sequencia atual, recorde) de dias seguidos com resposta. A atual conta ate' hoje
    ou ate' ontem -- quem ainda nao estudou hoje nao perde a sequencia de ontem."""
    if not days:
        return 0, 0
    ordered = sorted(days)
    best = run = 1
    for previous, current in zip(ordered, ordered[1:]):
        run = run + 1 if current - previous == timedelta(days=1) else 1
        best = max(best, run)
    day = today if today in days else today - timedelta(days=1)
    current = 0
    while day in days:
        current += 1
        day -= timedelta(days=1)
    return current, best


def week_start(day):
    """Segunda-feira da semana (mesma convencao do TruncWeek)."""
    return day - timedelta(days=day.weekday())


def weekly_series(rows: dict, today, weeks: int = WEEKS) -> list[dict]:
    """rows: {segunda_feira: (total, acertos)}. Completa as semanas sem resposta."""
    current = week_start(today)
    series = []
    for offset in range(weeks - 1, -1, -1):
        start = current - timedelta(weeks=offset)
        total, correct = rows.get(start, (0, 0))
        series.append(
            {
                "start": start,
                "total": total,
                "correct": correct,
                "percent": round(100 * correct / total) if total else None,
            }
        )
    return series


def report_precision(accepted: int, rejected: int):
    """Parte dos reportes ja' decididos que o professor aceitou. None sem decisao."""
    decided = accepted + rejected
    return round(100 * accepted / decided) if decided else None


def split_topics(rows: list[dict], top: int = TOP_TOPICS) -> tuple[list, list]:
    """(melhores, para reforcar) entre os topicos com MIN_ANSWERS+ respostas, sem repetir
    topico nas duas listas quando ha poucos (metade de cima vs metade de baixo)."""
    eligible = [
        {**row, "percent": percent(row["correct"], row["total"])} for row in rows if row["total"] >= MIN_ANSWERS
    ]
    eligible.sort(key=lambda row: (-row["percent"], row["topic"]))
    best_count = min(top, (len(eligible) + 1) // 2)
    best = eligible[:best_count]
    weak = sorted(eligible[best_count:], key=lambda row: (row["percent"], row["topic"]))[:top]
    return best, weak


# Geometria do grafico semanal (SVG gerado no servidor, sem lib JS). Colunas <= 24px,
# topo arredondado 4px e base reta (spec do skill dataviz); 0-100% no eixo.
CHART_WIDTH, CHART_TOP, CHART_BASE = 320, 12, 112
BAR_WIDTH, BAR_RADIUS = 20, 4


def _column_path(x: float, y: float, width: float, base: float, radius: float) -> str:
    height = base - y
    if height <= 0:
        return ""
    r = min(radius, height, width / 2)
    return (
        f"M{x:.1f},{base:.1f} V{y + r:.1f} Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
        f"H{x + width - r:.1f} Q{x + width:.1f},{y:.1f} {x + width:.1f},{y + r:.1f} V{base:.1f} Z"
    )


def weekly_chart(series: list[dict]) -> dict:
    """Pura: posicoes das colunas, dos rotulos e das linhas de grade (0/50/100%)."""
    band = CHART_WIDTH / len(series)
    plot_height = CHART_BASE - CHART_TOP
    bars = []
    for i, week in enumerate(series):
        x = i * band + (band - BAR_WIDTH) / 2
        value = week["percent"]
        y = CHART_BASE - plot_height * value / 100 if value is not None else CHART_BASE
        bars.append(
            {
                **week,
                "band_x": round(i * band, 1),
                "band_width": round(band, 1),
                "center": round(i * band + band / 2, 1),
                "path": _column_path(x, y, BAR_WIDTH, CHART_BASE, BAR_RADIUS) if value else "",
                "label_y": round(y - 4, 1),
                "is_current": i == len(series) - 1,
            }
        )
    grid = [{"y": round(CHART_BASE - plot_height * pct / 100, 1), "label": f"{pct}%"} for pct in (0, 50, 100)]
    return {
        "bars": bars,
        "grid": grid,
        "width": CHART_WIDTH,
        "height": CHART_BASE + 22,
        "base": CHART_BASE,
        "tick_y": CHART_BASE + 16,
        "has_data": any(week["total"] for week in series),
    }


# --- Consultas ---


def _totals(queryset) -> dict:
    return queryset.aggregate(total=Count("id"), correct=Count("id", filter=Q(is_correct=True)))


def build_user_stats(user) -> dict:
    from apps.moderation.models import Report, ReportStatus
    from apps.questions.models import (
        CommentReport,
        Question,
        QuestionAnswer,
        QuestionComment,
        QuestionStatus,
    )
    from apps.quiz.models import QuizAttempt

    today = timezone.localdate()
    answers = QuestionAnswer.objects.filter(user=user)

    # Resumo / desempenho
    summary = answers.aggregate(
        total=Count("id"), correct=Count("id", filter=Q(is_correct=True)), first=Min("answered_at")
    )
    window_start = week_start(today) - timedelta(weeks=WEEKS - 1)
    weekly = {
        row["week"].date(): (row["total"], row["correct"])
        for row in answers.filter(answered_at__date__gte=window_start)
        .annotate(week=TruncWeek("answered_at"))
        .values("week")
        .annotate(total=Count("id"), correct=Count("id", filter=Q(is_correct=True)))
    }
    days = set(answers.annotate(day=TruncDate("answered_at")).values_list("day", flat=True).distinct())
    current_streak, best_streak = streak(days, today)
    topic_rows = [
        {"topic": row["question__topic"], "total": row["total"], "correct": row["correct"]}
        for row in answers.values("question__topic").annotate(
            total=Count("id"), correct=Count("id", filter=Q(is_correct=True))
        )
    ]
    best_topics, weak_topics = split_topics(topic_rows)
    available = Question.objects.filter(status=QuestionStatus.ACTIVE).exclude(author=user)
    answered_available = (
        answers.filter(question__status=QuestionStatus.ACTIVE)
        .exclude(question__author=user)
        .values("question")
        .distinct()
        .count()
    )
    available_count = available.count()
    everyone = _totals(QuestionAnswer.objects.all())
    attempts = QuizAttempt.objects.filter(user=user)
    recent_attempts = [
        {"created_at": a.created_at, "score": a.score, "total": a.total, "percent": percent(a.score, a.total, 1)}
        for a in attempts.order_by("-created_at")[:5]
    ]

    # Como autor
    own = Question.objects.filter(author=user)
    own_by_status = {row["status"]: row["c"] for row in own.values("status").annotate(c=Count("id"))}
    answers_on_own = QuestionAnswer.objects.filter(question__author=user).exclude(user=user)
    own_totals = _totals(answers_on_own)
    per_question = [
        {
            "id": row["question"],
            "statement": row["question__statement"],
            "total": row["total"],
            "percent": percent(row["correct"], row["total"]),
        }
        for row in answers_on_own.values("question", "question__statement").annotate(
            total=Count("id"), correct=Count("id", filter=Q(is_correct=True))
        )
    ]
    rated = [q for q in per_question if q["percent"] is not None]
    hardest = min(rated, key=lambda q: (q["percent"], -q["total"]), default=None)
    easiest = max(rated, key=lambda q: (q["percent"], q["total"]), default=None)
    if easiest is not None and hardest is not None and easiest["id"] == hardest["id"]:
        easiest = None  # uma questao so' com 5+ respostas: nao aparece como "mais dificil" e "mais facil"
    comments_received = (
        QuestionComment.objects.filter(question__author=user, removed=False).exclude(author=user).count()
    )

    # Participacao
    reports_by_status = {
        row["status"]: row["c"] for row in Report.objects.filter(reporter=user).values("status").annotate(c=Count("id"))
    }
    accepted = reports_by_status.get(ReportStatus.ACCEPTED, 0)
    rejected = reports_by_status.get(ReportStatus.REJECTED, 0)

    return {
        "summary": {
            "answered": summary["total"],
            "correct": summary["correct"],
            "percent": percent(summary["correct"], summary["total"], 1),
            "since": summary["first"],
            "class_percent": percent(everyone["correct"], everyone["total"], MIN_CLASS_ANSWERS),
            "quizzes_completed": attempts.count(),
            "streak": current_streak,
            "best_streak": best_streak,
            "questions_created": sum(own_by_status.values()),
        },
        "weekly": weekly_chart(weekly_series(weekly, today)),
        "best_topics": best_topics,
        "weak_topics": weak_topics,
        "coverage": {
            "answered": answered_available,
            "available": available_count,
            "percent": percent(answered_available, available_count, 1),
        },
        "recent_attempts": recent_attempts,
        "author": {
            "active": own_by_status.get(QuestionStatus.ACTIVE, 0),
            "reported": own_by_status.get(QuestionStatus.REPORTED, 0),
            "removed": own_by_status.get(QuestionStatus.REMOVED, 0),
            "answers": own_totals["total"],
            "percent": percent(own_totals["correct"], own_totals["total"], 1),
            "most_answered": max(per_question, key=lambda q: (q["total"], -q["id"]), default=None),
            "hardest": hardest,
            "easiest": easiest,
            "comments_received": comments_received,
        },
        "participation": {
            "comments_made": QuestionComment.objects.filter(author=user, removed=False).count(),
            "reports_pending": reports_by_status.get(ReportStatus.PENDING, 0),
            "reports_accepted": accepted,
            "reports_rejected": rejected,
            "report_precision": report_precision(accepted, rejected),
            "comment_reports": CommentReport.objects.filter(reporter=user).count(),
        },
    }
