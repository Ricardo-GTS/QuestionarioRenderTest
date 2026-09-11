import pytest

from app.services.runtime_settings import update_settings


def test_update_settings_rejects_similarity_threshold_out_of_range():
    with pytest.raises(ValueError):
        update_settings(db=None, similarity_threshold=1.5)


def test_update_settings_rejects_zero_similarity_threshold():
    with pytest.raises(ValueError):
        update_settings(db=None, similarity_threshold=0)


def test_update_settings_rejects_non_positive_quiz_size():
    with pytest.raises(ValueError):
        update_settings(db=None, quiz_size=0)


def test_update_settings_rejects_non_positive_report_threshold():
    with pytest.raises(ValueError):
        update_settings(db=None, report_threshold=-1)
