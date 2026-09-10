from app.models.enums import QuestionStatus
from app.services.moderation import should_flag


def test_should_flag_true_when_reports_reach_threshold():
    assert should_flag(report_count=3, threshold=3, current_status=QuestionStatus.ACTIVE) is True


def test_should_flag_false_below_threshold():
    assert should_flag(report_count=2, threshold=3, current_status=QuestionStatus.ACTIVE) is False


def test_should_flag_false_when_already_flagged():
    assert should_flag(report_count=5, threshold=3, current_status=QuestionStatus.REPORTED) is False
