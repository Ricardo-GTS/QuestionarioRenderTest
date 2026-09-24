"""Casca do redesign: barra de baixo (4 abas), pagina Perfil, trilha de progresso do
Treinar, atalhos (quiz.js) e mensagens de erro com a classe nova."""

import re

import pytest
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.urls import reverse

from apps.accounts.models import User
from apps.questions.models import Question
from conftest import _fake_get_embedding

pytestmark = pytest.mark.django_db


def _user(email="aluno@example.com", number="22220000"):
    return User.objects.create_user(email=email, name="Aluno Teste", password="x" * 8, registration_number=number)


def _tabbar(html):
    match = re.search(r'<nav class="tabbar".*?</nav>', html, re.S)
    return match.group(0) if match else None


def test_tabbar_has_four_tabs_and_marks_current(client):
    client.force_login(_user())
    tabbar = _tabbar(client.get(reverse("questions:mine")).content.decode())
    assert tabbar is not None
    assert [label for label in re.findall(r"<span>([^<]+)</span>", tabbar)] == ["Treinar", "Criar", "Minhas", "Perfil"]
    current = re.findall(r'<a href="([^"]+)" aria-current="page"', tabbar)
    assert current == [reverse("questions:mine")]


def test_tabbar_perfil_is_current_on_stats(client):
    client.force_login(_user())
    tabbar = _tabbar(client.get(reverse("accounts:stats")).content.decode())
    assert re.findall(r'<a href="([^"]+)" aria-current="page"', tabbar) == [reverse("accounts:profile")]


def test_visitor_has_no_tabbar(client):
    html = client.get(reverse("accounts:login")).content.decode()
    assert _tabbar(html) is None
    assert "has-tabbar" not in html


def test_profile_links_for_student(client):
    client.force_login(_user())
    html = client.get(reverse("accounts:profile")).content.decode()
    for name in ("accounts:interactions", "accounts:stats", "accounts:account"):
        assert f'href="{reverse(name)}"' in html
    assert f'href="{reverse("moderation:dashboard")}"' not in html
    assert f'action="{reverse("accounts:logout")}"' in html
    assert "Sair" in html


def test_profile_shows_admin_link_for_admin(client):
    client.force_login(_user(email="admin@example.com", number="33330000"))
    html = client.get(reverse("accounts:profile")).content.decode()
    assert f'href="{reverse("moderation:dashboard")}"' in html


def test_profile_requires_login(client):
    resp = client.get(reverse("accounts:profile"))
    assert resp.status_code == 302


def test_error_message_uses_danger_class(rf):
    from django.contrib.messages.storage.base import Message

    assert Message(messages.ERROR, "x").tags == "danger"


@pytest.fixture
def started_quiz(client):
    from apps.core.models import AppSettings

    app_settings = AppSettings.get_solo()
    app_settings.quiz_size = 3
    app_settings.save()
    author = _user(email="autor@example.com", number="11110000")
    for i in range(3):
        Question.objects.create(
            author=author, statement=f"Pergunta {i}", correct_answer=True, topic="Geral",
            citations_references="Livro", pertinence="p", embedding=_fake_get_embedding(f"Pergunta {i}"),
        )
    client.force_login(_user())
    client.get(reverse("quiz:start"))
    return client


def _states(html):
    track = re.search(r'<ol class="track".*?</ol>', html, re.S).group(0)
    return re.findall(r'<li class="is-(\w+)', track)


def test_progress_track_states(started_quiz):
    client = started_quiz
    ids = client.session["quiz_question_ids"]
    assert _states(client.get(reverse("quiz:start")).content.decode()) == ["current", "pending", "pending"]

    client.post(reverse("quiz:answer"), {"answer": "true", "question_id": ids[0]})  # certa
    client.post(reverse("quiz:next"), {"question_id": ids[0]})
    client.post(reverse("quiz:answer"), {"answer": "false", "question_id": ids[1]})  # errada
    html = client.get(reverse("quiz:start")).content.decode()
    assert _states(html) == ["ok", "wrong", "pending"]
    assert 'class="is-wrong is-current"' in html  # respondida, ainda sem clicar Proxima


def test_quiz_js_served_and_referenced(started_quiz):
    assert finders.find("quiz/quiz.js")
    html = started_quiz.get(reverse("quiz:start")).content.decode()
    assert "quiz/quiz.js" in html
