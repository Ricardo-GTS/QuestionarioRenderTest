from pydantic import BaseModel


class QuizQuestionOut(BaseModel):
    id: int
    statement: str
    category: str | None


class QuizOut(BaseModel):
    questions: list[QuizQuestionOut]


class QuizAnswer(BaseModel):
    question_id: int
    answer: bool


class QuizSubmit(BaseModel):
    answers: list[QuizAnswer]


class QuestionFeedback(BaseModel):
    question_id: int
    statement: str
    correct_answer: bool
    given_answer: bool | None
    is_correct: bool


class QuizResult(BaseModel):
    score: int
    total: int
    feedback: list[QuestionFeedback]
