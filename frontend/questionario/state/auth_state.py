import reflex as rx

from questionario import api_client
from questionario.api_client import ApiError


class AuthState(rx.State):
    token: str = rx.LocalStorage("")
    user_id: int = 0
    user_name: str = ""
    user_email: str = ""
    is_admin: bool = False

    name: str = ""
    email: str = ""
    password: str = ""
    error_message: str = ""

    edit_name: str = ""
    edit_email: str = ""
    edit_password: str = ""
    account_message: str = ""
    account_error: str = ""
    confirm_delete: bool = False

    @rx.var
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def set_name(self, value: str) -> None:
        self.name = value

    def set_email(self, value: str) -> None:
        self.email = value

    def set_password(self, value: str) -> None:
        self.password = value

    def set_edit_name(self, value: str) -> None:
        self.edit_name = value

    def set_edit_email(self, value: str) -> None:
        self.edit_email = value

    def set_edit_password(self, value: str) -> None:
        self.edit_password = value

    def _reset_form(self) -> None:
        self.name = ""
        self.email = ""
        self.password = ""
        self.error_message = ""

    async def handle_register(self):
        self.error_message = ""
        try:
            await api_client.register(self.name, self.email, self.password)
        except ApiError as exc:
            self.error_message = str(exc.detail) if exc.detail else "Nao foi possivel cadastrar."
            return
        return await self.handle_login()

    async def handle_login(self):
        self.error_message = ""
        try:
            data = await api_client.login(self.email, self.password)
        except ApiError:
            self.error_message = "Email ou senha invalidos."
            return

        self.token = data["access_token"]
        try:
            me = await api_client.get_me(self.token)
            self.user_id = me["id"]
            self.user_name = me["name"]
            self.user_email = me["email"]
            self.is_admin = me.get("is_admin", False)
        except ApiError:
            pass

        self._reset_form()
        return rx.redirect("/")

    async def handle_google_login(self, response: dict):
        self.error_message = ""
        credential = response.get("credential")
        if not credential:
            self.error_message = "Login com Google falhou."
            return

        try:
            data = await api_client.login_with_google(credential)
        except ApiError:
            self.error_message = "Nao foi possivel entrar com Google."
            return

        self.token = data["access_token"]
        try:
            me = await api_client.get_me(self.token)
            self.user_id = me["id"]
            self.user_name = me["name"]
            self.user_email = me["email"]
            self.is_admin = me.get("is_admin", False)
        except ApiError:
            pass

        self._reset_form()
        return rx.redirect("/")

    def logout(self):
        self.token = ""
        self.user_id = 0
        self.user_name = ""
        self.user_email = ""
        self.is_admin = False
        return rx.redirect("/login")

    async def load_current_user(self):
        if not self.token:
            return rx.redirect("/login")
        try:
            me = await api_client.get_me(self.token)
            self.user_id = me["id"]
            self.user_name = me["name"]
            self.user_email = me["email"]
            self.is_admin = me.get("is_admin", False)
            self.edit_name = me["name"]
            self.edit_email = me["email"]
        except ApiError:
            self.token = ""
            return rx.redirect("/login")

    async def require_admin(self):
        """Usado no on_mount das paginas /admin/* -- garante sessao valida e acesso de admin."""
        if not self.token:
            return rx.redirect("/login")
        try:
            me = await api_client.get_me(self.token)
        except ApiError:
            self.token = ""
            return rx.redirect("/login")

        self.user_id = me["id"]
        self.user_name = me["name"]
        self.user_email = me["email"]
        self.is_admin = me.get("is_admin", False)
        if not self.is_admin:
            return rx.redirect("/")

    async def update_account(self):
        self.account_message = ""
        self.account_error = ""
        try:
            me = await api_client.update_me(
                self.token,
                name=self.edit_name or None,
                email=self.edit_email or None,
                password=self.edit_password or None,
            )
        except ApiError as exc:
            self.account_error = str(exc.detail) if exc.detail else "Nao foi possivel atualizar a conta."
            return

        self.user_name = me["name"]
        self.user_email = me["email"]
        self.edit_password = ""
        self.account_message = "Dados atualizados com sucesso."

    def ask_delete_account(self) -> None:
        self.confirm_delete = True

    def cancel_delete_account(self) -> None:
        self.confirm_delete = False

    async def delete_account(self):
        try:
            await api_client.delete_me(self.token)
        except ApiError:
            self.account_error = "Nao foi possivel excluir a conta."
            self.confirm_delete = False
            return
        self.token = ""
        self.user_id = 0
        self.user_name = ""
        self.user_email = ""
        self.confirm_delete = False
        return rx.redirect("/login")
