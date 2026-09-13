import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError
from questionario.state.auth_state import AuthState


class StatsState(rx.State):
    accepted_reports_count: int = 0
    rejected_reports_count: int = 0
    questions_removed_count: int = 0
    loading: bool = False
    error_message: str = ""

    async def load_stats(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            data = await api_client.get_my_reputation(auth.token)
            self.accepted_reports_count = data["accepted_reports_count"]
            self.rejected_reports_count = data["rejected_reports_count"]
            self.questions_removed_count = data["questions_removed_count"]
        except ApiError:
            self.error_message = "Nao foi possivel carregar suas estatisticas."
        finally:
            self.loading = False
