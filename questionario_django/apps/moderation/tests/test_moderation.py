"""Porte de backend/tests/test_moderation.py -- puro, sem banco."""

from apps.moderation.services import should_flag
from apps.questions.models import QuestionStatus


def test_flags_when_threshold_reached():
    assert should_flag(report_count=3, threshold=3, current_status=QuestionStatus.ACTIVE) is True


def test_does_not_flag_below_threshold():
    assert should_flag(report_count=2, threshold=3, current_status=QuestionStatus.ACTIVE) is False


def test_does_not_reflag_already_reported_question():
    assert should_flag(report_count=5, threshold=3, current_status=QuestionStatus.REPORTED) is False
