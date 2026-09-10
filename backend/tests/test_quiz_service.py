from types import SimpleNamespace

from app.services.quiz import score_quiz


def _question(id_, statement, correct_answer):
    return SimpleNamespace(id=id_, statement=statement, correct_answer=correct_answer)


def test_score_quiz_counts_correct_answers():
    questions = [
        _question(1, "Pergunta 1", True),
        _question(2, "Pergunta 2", False),
        _question(3, "Pergunta 3", True),
    ]
    answers = {1: True, 2: False, 3: False}

    result = score_quiz(questions, answers)

    assert result["score"] == 2
    assert result["total"] == 3
    assert result["feedback"][2]["is_correct"] is False


def test_score_quiz_missing_answer_counts_as_incorrect():
    questions = [_question(1, "Pergunta 1", True)]

    result = score_quiz(questions, answers={})

    assert result["score"] == 0
    assert result["feedback"][0]["given_answer"] is None
    assert result["feedback"][0]["is_correct"] is False
