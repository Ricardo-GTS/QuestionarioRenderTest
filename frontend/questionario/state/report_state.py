import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError
from questionario.state.auth_state import AuthState


class ReportState(rx.State):
    show_modal: bool = False
    question_id: int = 0
    reason: str = ""
    reason_category: str = ""
    success_message: str = ""
    error_message: str = ""

    def open_modal(self, question_id: int) -> None:
        self.show_modal = True
        self.question_id = question_id
        self.reason = ""
        self.reason_category = ""
        self.success_message = ""
        self.error_message = ""

    def close_modal(self) -> None:
        self.show_modal = False

    def set_reason(self, value: str) -> None:
        self.reason = value

    def set_reason_category(self, value: str) -> None:
        self.reason_category = value

    async def submit_report(self):
        auth = await self.get_state(AuthState)
        self.error_message = ""
        if not self.reason.strip():
            self.error_message = "Descreva o motivo do reporte."
            return
        try:
            await api_client.report_question(
                auth.token, self.question_id, self.reason, self.reason_category or None
            )
        except ApiError:
            self.error_message = "Nao foi possivel enviar o reporte."
            return
        self.success_message = "Reporte enviado. Obrigado!"
        self.show_modal = False
