import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState


def account_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Minha conta"),
                rx.cond(
                    AuthState.account_message != "",
                    rx.text(AuthState.account_message, color="green"),
                ),
                rx.cond(
                    AuthState.account_error != "",
                    rx.text(AuthState.account_error, color="red"),
                ),
                rx.input(
                    placeholder="Nome",
                    value=AuthState.edit_name,
                    on_change=AuthState.set_edit_name,
                    width="100%",
                ),
                rx.input(
                    placeholder="Email",
                    value=AuthState.edit_email,
                    on_change=AuthState.set_edit_email,
                    width="100%",
                ),
                rx.input(
                    placeholder="Nova senha (opcional)",
                    type="password",
                    value=AuthState.edit_password,
                    on_change=AuthState.set_edit_password,
                    width="100%",
                ),
                rx.button("Salvar alteracoes", on_click=AuthState.update_account, width="100%"),
                rx.divider(),
                rx.cond(
                    AuthState.confirm_delete,
                    rx.vstack(
                        rx.text("Tem certeza? Essa acao nao pode ser desfeita.", color="red"),
                        rx.hstack(
                            rx.button(
                                "Cancelar", on_click=AuthState.cancel_delete_account, variant="soft"
                            ),
                            rx.button(
                                "Confirmar exclusao",
                                on_click=AuthState.delete_account,
                                color_scheme="red",
                            ),
                            spacing="3",
                        ),
                        spacing="2",
                    ),
                    rx.button(
                        "Excluir minha conta",
                        on_click=AuthState.ask_delete_account,
                        color_scheme="red",
                        variant="outline",
                    ),
                ),
                spacing="3",
                width=["90%", "70%", "400px"],
                padding="1em",
            ),
        ),
        on_mount=AuthState.load_current_user,
        width="100%",
        spacing="0",
    )
