"""Porte de backend/tests/test_quiz_service.py -- puro, sem banco."""

from types import SimpleNamespace

from apps.quiz.services import score_quiz


def _q(id_, correct_answer):
    return SimpleNamespace(id=id_, statement=f"pergunta {id_}", correct_answer=correct_answer)


def test_counts_correct_answers():
    questions = [_q(1, True), _q(2, False)]
    result = score_quiz(questions, {1: True, 2: False})
    assert result["score"] == 2
    assert result["total"] == 2


def test_missing_answer_counts_as_incorrect():
    questions = [_q(1, True)]
    result = score_quiz(questions, {})
    assert result["score"] == 0
    assert result["feedback"][0]["given_answer"] is None
    assert result["feedback"][0]["is_correct"] is False
