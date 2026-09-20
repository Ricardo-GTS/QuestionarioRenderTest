"""Porte de backend/tests/test_stats.py -- puro, sem banco."""

from apps.moderation.services import compute_average_score_percent


def test_average_of_multiple_attempts():
    result = compute_average_score_percent([(5, 10), (10, 10)])
    assert result == 75.0


def test_empty_list_returns_none():
    assert compute_average_score_percent([]) is None


def test_ignores_attempts_with_zero_total():
    result = compute_average_score_percent([(0, 0), (5, 10)])
    assert result == 50.0
