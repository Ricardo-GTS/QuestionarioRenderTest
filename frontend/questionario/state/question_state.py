import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError
from questionario.state.auth_state import AuthState


class QuestionState(rx.State):
    statement: str = ""
    correct_answer: str = "true"
    category: str = ""

    success_message: str = ""
    error_message: str = ""
    similar_questions: list[dict] = []

    def set_statement(self, value: str) -> None:
        self.statement = value

    def set_correct_answer(self, value: str) -> None:
        self.correct_answer = value

    def set_category(self, value: str) -> None:
        self.category = value

    async def handle_create_question(self):
        auth = await self.get_state(AuthState)
        self.success_message = ""
        self.error_message = ""
        self.similar_questions = []

        if not self.statement.strip():
            self.error_message = "Digite o enunciado da pergunta."
            return

        try:
            await api_client.create_question(
                auth.token,
                statement=self.statement,
                correct_answer=self.correct_answer == "true",
                category=self.category or None,
            )
        except ApiError as exc:
            if exc.status_code == 409 and isinstance(exc.detail, dict):
                self.error_message = exc.detail.get("message", "Pergunta muito similar a uma existente.")
                self.similar_questions = exc.detail.get("similar_questions", [])
            else:
                self.error_message = "Nao foi possivel criar a pergunta. Tente novamente."
            return

        self.success_message = "Pergunta criada com sucesso!"
        self.statement = ""
        self.category = ""
