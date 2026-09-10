import reflex as rx

from questionario.state.auth_state import AuthState


def navbar() -> rx.Component:
    return rx.hstack(
        rx.link(rx.heading("Questionario", size="5"), href="/"),
        rx.spacer(),
        rx.cond(
            AuthState.is_authenticated,
            rx.hstack(
                rx.link("Questionario", href="/quiz"),
                rx.link("Conta", href="/account"),
                rx.button("Sair", on_click=AuthState.logout, size="2", variant="soft"),
                spacing="4",
                align="center",
            ),
            rx.hstack(
                rx.link("Entrar", href="/login"),
                rx.link("Cadastrar", href="/register"),
                spacing="4",
            ),
        ),
        width="100%",
        padding="1em",
        border_bottom="1px solid #e2e2e2",
        align="center",
    )
