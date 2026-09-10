import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError
from questionario.state.auth_state import AuthState


class QuizState(rx.State):
    questions: list[dict] = []
    current_index: int = 0
    answers: dict[int, bool] = {}

    submitted: bool = False
    score: int = 0
    total: int = 0
    feedback: list[dict] = []

    loading: bool = False
    error_message: str = ""
    finished: bool = False

    @rx.var
    def current_question(self) -> dict:
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return {}

    @rx.var
    def progress_label(self) -> str:
        if not self.questions:
            return ""
        return f"{self.current_index + 1} / {len(self.questions)}"

    async def start_quiz(self):
        auth = await self.get_state(AuthState)
        self.error_message = ""
        self.submitted = False
        self.score = 0
        self.total = 0
        self.feedback = []
        self.answers = {}
        self.current_index = 0
        self.finished = False
        self.loading = True
        try:
            data = await api_client.get_quiz(auth.token)
            self.questions = data.get("questions", [])
            if not self.questions:
                self.error_message = "Nao ha perguntas suficientes para montar um questionario ainda."
        except ApiError:
            self.error_message = "Nao foi possivel carregar o questionario."
        finally:
            self.loading = False

    async def answer_current(self, value: bool):
        question = self.current_question
        if not question:
            return
        self.answers[question["id"]] = value
        if self.current_index + 1 < len(self.questions):
            self.current_index += 1
        else:
            self.finished = True
            return await self.submit()

    async def submit(self):
        auth = await self.get_state(AuthState)
        payload = [{"question_id": qid, "answer": value} for qid, value in self.answers.items()]
        try:
            result = await api_client.submit_quiz(auth.token, payload)
        except ApiError:
            self.error_message = "Nao foi possivel enviar as respostas."
            return
        self.score = result["score"]
        self.total = result["total"]
        self.feedback = result["feedback"]
        self.submitted = True
