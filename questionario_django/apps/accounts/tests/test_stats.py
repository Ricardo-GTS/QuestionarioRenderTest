"""Pagina de Estatisticas do aluno + treino por topico no quiz."""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts import stats
from apps.accounts.models import User
from apps.moderation.models import Report
from apps.questions.models import Question, QuestionAnswer, QuestionComment, QuestionStatus
from apps.quiz.models import QuizAttempt
from conftest import _fake_get_embedding

TODAY = date(2026, 9, 24)  # quinta-feira


# --- funcoes puras ---


def test_streak():
    d = lambda n: TODAY - timedelta(days=n)  # noqa: E731
    assert stats.streak(set(), TODAY) == (0, 0)
    assert stats.streak({TODAY}, TODAY) == (1, 1)
    assert stats.streak({d(1), d(2)}, TODAY) == (2, 2)  # nao estudou hoje: ontem ainda vale
    assert stats.streak({d(2), d(3)}, TODAY) == (0, 2)  # buraco ontem: zerou
    assert stats.streak({TODAY, d(1), d(5), d(6), d(7), d(8)}, TODAY) == (2, 4)  # recorde maior


def test_weekly_series_fills_empty_weeks():
    monday = stats.week_start(TODAY)
    series = stats.weekly_series({monday: (10, 7), monday - timedelta(weeks=2): (4, 1)}, TODAY)
    assert len(series) == 8
    assert series[-1] == {"start": monday, "total": 10, "correct": 7, "percent": 70}
    assert series[-2]["total"] == 0 and series[-2]["percent"] is None
    assert series[-3]["percent"] == 25
    assert series[0]["start"] == monday - timedelta(weeks=7)


def test_weekly_chart_geometry():
    series = stats.weekly_series({stats.week_start(TODAY): (4, 2)}, TODAY)
    chart = stats.weekly_chart(series)
    assert chart["has_data"]
    assert [bar["path"] == "" for bar in chart["bars"]] == [True] * 7 + [False]
    assert chart["bars"][-1]["is_current"]
    assert [g["label"] for g in chart["grid"]] == ["0%", "50%", "100%"]


def test_percent_and_precision():
    assert stats.percent(3, 4) is None  # abaixo do minimo
    assert stats.percent(4, 5) == 80
    assert stats.percent(0, 0, 1) is None
    assert stats.report_precision(0, 0) is None
    assert stats.report_precision(3, 0) == 100
    assert stats.report_precision(1, 3) == 25


def test_split_topics_never_repeats():
    row = lambda t, total, c: {"topic": t, "total": total, "correct": c}  # noqa: E731
    best, weak = stats.split_topics([row("A", 5, 5)])
    assert [r["topic"] for r in best] == ["A"] and weak == []
    best, weak = stats.split_topics([row("A", 5, 5), row("B", 5, 1), row("C", 4, 0)])  # C abaixo do minimo
    assert [r["topic"] for r in best] == ["A"] and [r["topic"] for r in weak] == ["B"]
    rows = [row(t, 10, c) for t, c in zip("ABCDEFGH", range(10, 2, -1))]
    best, weak = stats.split_topics(rows)
    assert len(best) == 3 and len(weak) == 3
    assert not {r["topic"] for r in best} & {r["topic"] for r in weak}
    assert weak[0]["topic"] == "H"  # o pior primeiro


# --- pagina ---


def _user(email, reg):
    return User.objects.create_user(email=email, name=email.split("@")[0], password="x" * 8, registration_number=reg)


def _question(author, statement, topic="Geral", correct=True, status=QuestionStatus.ACTIVE):
    return Question.objects.create(
        author=author, statement=statement, correct_answer=correct, topic=topic,
        citations_references="r", pertinence="p", embedding=_fake_get_embedding(statement), status=status,
    )


def _answers(user, question, correct, wrong):
    for _ in range(correct):
        QuestionAnswer.objects.create(question=question, user=user, is_correct=True)
    for _ in range(wrong):
        QuestionAnswer.objects.create(question=question, user=user, is_correct=False)


@pytest.fixture
def student(client):
    user = _user("aluno@example.com", "10000001")
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_empty_state(client, student):
    resp = client.get(reverse("accounts:stats"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "para ver seu desempenho" in html
    assert "ainda não criou questões" in html


@pytest.mark.django_db
def test_performance_numbers(client, student):
    author = _user("autor@example.com", "10000002")
    geo = _question(author, "Geo", topic="Geografia")
    his = _question(author, "His", topic="Historia")
    _question(author, "Nao respondida")
    _answers(student, geo, correct=5, wrong=0)
    _answers(student, his, correct=1, wrong=4)
    QuizAttempt.objects.create(user=student, score=7, total=10)

    s = client.get(reverse("accounts:stats")).context["stats"]
    assert s["summary"]["answered"] == 10
    assert s["summary"]["percent"] == 60
    assert s["summary"]["quizzes_completed"] == 1
    assert s["summary"]["streak"] == 1
    assert [t["topic"] for t in s["best_topics"]] == ["Geografia"]
    assert [t["topic"] for t in s["weak_topics"]] == ["Historia"]
    assert s["coverage"] == {"answered": 2, "available": 3, "percent": 67}
    assert s["weekly"]["bars"][-1]["total"] == 10
    assert s["recent_attempts"][0]["percent"] == 70
    html = client.get(reverse("accounts:stats")).content.decode()
    assert "Treinar este tópico" in html and "topico=Historia" in html


@pytest.mark.django_db
def test_class_average_needs_20_answers(client, student):
    author = _user("autor@example.com", "10000002")
    q = _question(author, "Q")
    other = _user("outro@example.com", "10000003")
    _answers(other, q, correct=10, wrong=9)  # 19 respostas no sistema
    assert client.get(reverse("accounts:stats")).context["stats"]["summary"]["class_percent"] is None
    _answers(other, q, correct=1, wrong=0)  # 20
    assert client.get(reverse("accounts:stats")).context["stats"]["summary"]["class_percent"] == 55


@pytest.mark.django_db
def test_author_section(client, student):
    hard = _question(student, "Questao dificil")
    easy = _question(student, "Questao facil")
    _question(student, "Removida", status=QuestionStatus.REMOVED)
    others = [_user(f"o{i}@example.com", f"2000000{i}") for i in range(2)]
    _answers(others[0], hard, correct=1, wrong=4)
    _answers(others[1], easy, correct=5, wrong=1)
    QuestionComment.objects.create(question=easy, author=others[0], text="oi")
    QuestionComment.objects.create(question=easy, author=student, text="meu")  # nao conta como recebido

    a = client.get(reverse("accounts:stats")).context["stats"]["author"]
    assert (a["active"], a["removed"]) == (2, 1)
    assert a["answers"] == 11 and a["percent"] == 55
    assert a["most_answered"]["statement"] == "Questao facil"
    assert a["hardest"]["statement"] == "Questao dificil"
    assert a["easiest"]["statement"] == "Questao facil"
    assert a["comments_received"] == 1


@pytest.mark.django_db
def test_single_rated_question_is_not_both_hardest_and_easiest(client, student):
    q = _question(student, "Unica")
    _answers(_user("o@example.com", "20000001"), q, correct=3, wrong=2)
    a = client.get(reverse("accounts:stats")).context["stats"]["author"]
    assert a["hardest"]["statement"] == "Unica" and a["easiest"] is None


@pytest.mark.django_db
def test_participation_precision(client, student):
    author = _user("autor@example.com", "10000002")
    for i, status in enumerate(["accepted", "accepted", "rejected", "pending"]):
        Report.objects.create(question=_question(author, f"R{i}"), reporter=student, reason="motivo", status=status)
    p = client.get(reverse("accounts:stats")).context["stats"]["participation"]
    assert (p["reports_pending"], p["reports_accepted"], p["reports_rejected"]) == (1, 2, 1)
    assert p["report_precision"] == 67


@pytest.mark.django_db
def test_days_are_counted_in_local_timezone(client, student, settings):
    """23h30 em Recife = 02h30 UTC do dia seguinte: tem que contar no dia LOCAL."""
    from django.db.models.functions import TruncDate

    assert settings.TIME_ZONE == "America/Recife"
    q = _question(_user("autor@example.com", "10000002"), "Q")
    QuestionAnswer.objects.create(question=q, user=student, is_correct=True)
    QuestionAnswer.objects.update(answered_at=datetime(2026, 9, 21, 2, 30, tzinfo=dt_timezone.utc))
    [day] = QuestionAnswer.objects.annotate(day=TruncDate("answered_at")).values_list("day", flat=True)
    assert day == date(2026, 9, 20)  # em UTC seria 21/09


@pytest.mark.django_db
def test_query_count_does_not_grow(client, student, django_assert_max_num_queries):
    author = _user("autor@example.com", "10000002")
    qs = [_question(author, f"Q{i}", topic=f"T{i % 3}") for i in range(5)]
    for q in qs:
        _answers(student, q, 1, 0)
    with django_assert_max_num_queries(40) as small:
        client.get(reverse("accounts:stats"))
    more = [_question(author, f"M{i}", topic=f"T{i % 7}") for i in range(10)]
    for q in more:
        _answers(student, q, 3, 2)
    with django_assert_max_num_queries(len(small.captured_queries)):
        client.get(reverse("accounts:stats"))


# --- treino por topico ---


@pytest.mark.django_db
def test_train_topic_quiz(client, student):
    author = _user("autor@example.com", "10000002")
    for i in range(3):
        _question(author, f"Geo {i}", topic="Geografia")
    _question(author, "Outra", topic="Historia")
    _question(student, "Minha de geo", topic="Geografia")  # propria: nunca no quiz

    resp = client.get(reverse("quiz:start") + "?novo=1&topico=Geografia")
    ids = client.session["quiz_question_ids"]
    topics = set(Question.objects.filter(pk__in=ids).values_list("topic", flat=True))
    assert topics == {"Geografia"} and len(ids) == 3
    html = resp.content.decode()
    assert "Treino: Geografia" in html
    assert "topico=Geografia" in html  # Recomecar mantem o topico


@pytest.mark.django_db
def test_unknown_topic_falls_back_and_empty_topic_message(client, student):
    author = _user("autor@example.com", "10000002")
    _question(author, "Geo", topic="Geografia")
    _question(student, "So' minha", topic="Solitario")
    client.get(reverse("quiz:start") + "?novo=1&topico=NaoExiste")
    assert client.session["quiz_topic"] is None
    assert len(client.session["quiz_question_ids"]) == 1

    resp = client.get(reverse("quiz:start") + "?novo=1&topico=Solitario")
    assert "Não há questões disponíveis no tópico" in resp.content.decode()
