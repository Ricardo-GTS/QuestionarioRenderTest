from app.services.stats import compute_average_score_percent


def test_compute_average_score_percent_basic():
    # 2 tentativas: 5/10 (50%) e 8/10 (80%) -> media 65%
    assert compute_average_score_percent([(5, 10), (8, 10)]) == 65.0


def test_compute_average_score_percent_no_attempts_returns_none():
    assert compute_average_score_percent([]) is None


def test_compute_average_score_percent_ignores_zero_total():
    assert compute_average_score_percent([(0, 0), (10, 10)]) == 100.0
