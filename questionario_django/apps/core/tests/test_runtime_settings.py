"""Porte de backend/tests/test_runtime_settings.py -- testa so a validacao,
que roda antes de qualquer acesso ao banco (por isso nao precisa de @pytest.mark.django_db)."""

import pytest

from apps.core.services import update_settings


def test_similarity_threshold_must_be_greater_than_zero():
    with pytest.raises(ValueError):
        update_settings(similarity_threshold=0)


def test_similarity_threshold_must_be_at_most_one():
    with pytest.raises(ValueError):
        update_settings(similarity_threshold=1.5)


def test_quiz_size_must_be_positive():
    with pytest.raises(ValueError):
        update_settings(quiz_size=0)


def test_report_threshold_must_be_positive():
    with pytest.raises(ValueError):
        update_settings(report_threshold=-1)
