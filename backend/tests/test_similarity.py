from types import SimpleNamespace

from app.services.similarity import filter_by_threshold


def test_filter_by_threshold_keeps_matches_at_or_above_limiar():
    q1 = SimpleNamespace(id=1)
    q2 = SimpleNamespace(id=2)
    q3 = SimpleNamespace(id=3)

    # similaridade = 1 - distancia
    rows = [
        (q1, 0.10),  # similaridade 0.90 -> acima do limiar
        (q2, 0.25),  # similaridade 0.75 -> exatamente no limiar
        (q3, 0.40),  # similaridade 0.60 -> abaixo do limiar
    ]

    matches = filter_by_threshold(rows, threshold=0.75)

    assert {m.question.id for m in matches} == {1, 2}


def test_filter_by_threshold_empty_when_nothing_similar():
    q1 = SimpleNamespace(id=1)
    rows = [(q1, 0.9)]

    matches = filter_by_threshold(rows, threshold=0.75)

    assert matches == []
