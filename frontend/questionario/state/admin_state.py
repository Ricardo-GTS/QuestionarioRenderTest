import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError
from questionario.models import AdminQuestionItem, question_item_from_api
from questionario.state.auth_state import AuthState

# --- Moderacao -------------------------------------------------------------


class AdminModerationState(rx.State):
    # rx.PropsBase (nao dict) pra rx.foreach aninhar de verdade sobre
    # question.reports -- ver questionario/models.py.
    questions: list[AdminQuestionItem] = []
    loading: bool = False
    error_message: str = ""
    success_message: str = ""

    async def load_reported(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            questions = await api_client.admin_list_pending_reports(auth.token)
            self.questions = [question_item_from_api(q) for q in questions]
        except ApiError:
            self.error_message = "Nao foi possivel carregar as perguntas reportadas."
        finally:
            self.loading = False

    async def approve_removal(self, question_id: int):
        auth = await self.get_state(AuthState)
        try:
            await api_client.admin_approve_removal(auth.token, question_id)
            self.success_message = "Remocao aprovada -- pergunta removida, reportes aceitos."
        except ApiError:
            self.error_message = "Nao foi possivel aprovar a remocao."
            return
        return await self.load_reported()

    async def reject_removal(self, question_id: int):
        auth = await self.get_state(AuthState)
        try:
            await api_client.admin_reject_removal(auth.token, question_id)
            self.success_message = "Remocao rejeitada -- pergunta mantida ativa, reportes rejeitados."
        except ApiError:
            self.error_message = "Nao foi possivel rejeitar a remocao."
            return
        return await self.load_reported()


# --- Perguntas removidas ------------------------------------------------------


class AdminRemovedState(rx.State):
    questions: list[dict] = []
    loading: bool = False
    error_message: str = ""
    success_message: str = ""

    editing_id: int = 0
    edit_statement: str = ""
    edit_correct_answer: str = "true"
    edit_category: str = ""

    def set_edit_statement(self, value: str) -> None:
        self.edit_statement = value

    def set_edit_correct_answer(self, value: str) -> None:
        self.edit_correct_answer = value

    def set_edit_category(self, value: str) -> None:
        self.edit_category = value

    async def load_removed(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            self.questions = await api_client.admin_list_questions(auth.token, status="removed")
        except ApiError:
            self.error_message = "Nao foi possivel carregar as perguntas removidas."
        finally:
            self.loading = False

    async def reactivate(self, question_id: int):
        auth = await self.get_state(AuthState)
        try:
            await api_client.admin_approve_question(auth.token, question_id)
            self.success_message = "Pergunta reativada."
        except ApiError:
            self.error_message = "Nao foi possivel reativar a pergunta."
            return
        return await self.load_removed()

    def start_edit(self, question: dict) -> None:
        self.editing_id = question["id"]
        self.edit_statement = question["statement"]
        self.edit_correct_answer = "true" if question["correct_answer"] else "false"
        self.edit_category = question["category"] or ""

    def cancel_edit(self) -> None:
        self.editing_id = 0

    async def save_edit(self):
        auth = await self.get_state(AuthState)
        try:
            await api_client.admin_update_question(
                auth.token,
                self.editing_id,
                statement=self.edit_statement,
                correct_answer=self.edit_correct_answer == "true",
                category=self.edit_category or None,
            )
            self.success_message = "Pergunta atualizada."
        except ApiError:
            self.error_message = "Nao foi possivel atualizar a pergunta."
            return
        self.editing_id = 0
        return await self.load_removed()


# --- Usuarios ---------------------------------------------------------------


class AdminUsersState(rx.State):
    users: list[dict] = []
    loading: bool = False
    error_message: str = ""
    confirm_delete_id: int = 0

    async def load_users(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            self.users = await api_client.admin_list_users(auth.token)
        except ApiError:
            self.error_message = "Nao foi possivel carregar os usuarios."
        finally:
            self.loading = False

    def ask_delete(self, user_id: int) -> None:
        self.confirm_delete_id = user_id

    def cancel_delete(self) -> None:
        self.confirm_delete_id = 0

    async def confirm_delete_user(self):
        auth = await self.get_state(AuthState)
        try:
            await api_client.admin_delete_user(auth.token, self.confirm_delete_id)
        except ApiError:
            self.error_message = "Nao foi possivel excluir o usuario."
            self.confirm_delete_id = 0
            return
        self.confirm_delete_id = 0
        return await self.load_users()


# --- Configuracoes ------------------------------------------------------------


class AdminSettingsState(rx.State):
    similarity_threshold: str = ""
    quiz_size: str = ""
    report_threshold: str = ""
    loading: bool = False
    error_message: str = ""
    success_message: str = ""

    def set_similarity_threshold(self, value: str) -> None:
        self.similarity_threshold = value

    def set_quiz_size(self, value: str) -> None:
        self.quiz_size = value

    def set_report_threshold(self, value: str) -> None:
        self.report_threshold = value

    async def load_settings(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            data = await api_client.admin_get_settings(auth.token)
            self.similarity_threshold = str(data["similarity_threshold"])
            self.quiz_size = str(data["quiz_size"])
            self.report_threshold = str(data["report_threshold"])
        except ApiError:
            self.error_message = "Nao foi possivel carregar as configuracoes."
        finally:
            self.loading = False

    async def save_settings(self):
        auth = await self.get_state(AuthState)
        self.error_message = ""
        self.success_message = ""
        try:
            similarity_threshold = float(self.similarity_threshold)
            quiz_size = int(self.quiz_size)
            report_threshold = int(self.report_threshold)
        except ValueError:
            self.error_message = "Valores invalidos -- confira os campos."
            return

        try:
            await api_client.admin_update_settings(
                auth.token,
                similarity_threshold=similarity_threshold,
                quiz_size=quiz_size,
                report_threshold=report_threshold,
            )
        except ApiError as exc:
            self.error_message = str(exc.detail) if exc.detail else "Nao foi possivel salvar."
            return
        self.success_message = "Configuracoes salvas."


# --- Dashboard ----------------------------------------------------------------


class AdminStatsState(rx.State):
    total_users: int = 0
    total_questions_active: int = 0
    total_questions_reported: int = 0
    total_questions_removed: int = 0
    total_reports: int = 0
    total_quiz_attempts: int = 0
    average_score_percent: float | None = None
    questions_by_category: list[dict] = []
    reports_by_category: list[dict] = []

    loading: bool = False
    error_message: str = ""

    async def load_stats(self):
        auth = await self.get_state(AuthState)
        self.loading = True
        self.error_message = ""
        try:
            data = await api_client.admin_get_stats(auth.token)
            self.total_users = data["total_users"]
            self.total_questions_active = data["total_questions_active"]
            self.total_questions_reported = data["total_questions_reported"]
            self.total_questions_removed = data["total_questions_removed"]
            self.total_reports = data["total_reports"]
            self.total_quiz_attempts = data["total_quiz_attempts"]
            self.average_score_percent = data["average_score_percent"]
            self.questions_by_category = data["questions_by_category"]
            self.reports_by_category = data["reports_by_category"]
        except ApiError:
            self.error_message = "Nao foi possivel carregar as estatisticas."
        finally:
            self.loading = False
