import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState
from questionario.style import FALSE_COLOR, FORCE_LIGHT_CLASS, TRUE_COLOR


def account_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Minha conta", size="7"),
                rx.cond(
                    AuthState.account_message != "",
                    rx.text(AuthState.account_message, color=TRUE_COLOR, weight="bold"),
                ),
                rx.cond(
                    AuthState.account_error != "",
                    rx.text(AuthState.account_error, color=FALSE_COLOR, weight="bold"),
                ),
                rx.input(
                    placeholder="Nome",
                    value=AuthState.edit_name,
                    on_change=AuthState.set_edit_name,
                    width="100%",
                    border_radius="0",
                ),
                rx.input(
                    placeholder="Email",
                    value=AuthState.edit_email,
                    on_change=AuthState.set_edit_email,
                    width="100%",
                    border_radius="0",
                ),
                rx.input(
                    placeholder="Nova senha (opcional)",
                    type="password",
                    value=AuthState.edit_password,
                    on_change=AuthState.set_edit_password,
                    width="100%",
                    border_radius="0",
                ),
                rx.button(
                    "Salvar alteracoes", on_click=AuthState.update_account, width="100%", border_radius="0"
                ),
                rx.divider(),
                rx.cond(
                    AuthState.confirm_delete,
                    rx.vstack(
                        rx.text(
                            "Tem certeza? Essa acao nao pode ser desfeita.",
                            color=FALSE_COLOR,
                            weight="bold",
                        ),
                        rx.hstack(
                            rx.button(
                                "Cancelar",
                                on_click=AuthState.cancel_delete_account,
                                variant="soft",
                                border_radius="0",
                            ),
                            rx.button(
                                "Confirmar exclusao",
                                on_click=AuthState.delete_account,
                                color_scheme="red",
                                border_radius="0",
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
                        border_radius="0",
                    ),
                ),
                spacing="3",
                align_items="start",
                width=["90%", "70%", "400px"],
                padding="1.5em",
            ),
        ),
        on_mount=AuthState.load_current_user,
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
