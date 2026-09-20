"""Porte de backend/tests/test_similarity.py -- puro, sem banco."""

from types import SimpleNamespace

from apps.questions.services import filter_by_threshold


def test_keeps_question_at_exact_threshold():
    question = SimpleNamespace(id=1, statement="x")
    rows = [(question, 0.25)]  # distance 0.25 -> similarity 0.75
    result = filter_by_threshold(rows, threshold=0.75)
    assert len(result) == 1
    assert result[0].similarity == 0.75


def test_filters_below_threshold():
    question = SimpleNamespace(id=1, statement="x")
    rows = [(question, 0.5)]  # similarity 0.5, abaixo do threshold 0.75
    result = filter_by_threshold(rows, threshold=0.75)
    assert result == []
