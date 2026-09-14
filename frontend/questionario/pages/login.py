import reflex as rx
from reflex_google_auth import google_login, google_oauth_provider

from questionario.state.auth_state import AuthState
from questionario.style import FALSE_COLOR, FORCE_LIGHT_CLASS, card_style


def login_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Entrar", size="7"),
            rx.text("Continue de onde parou -- suas perguntas e reportes estao te esperando.", color="var(--gray-11)"),
            rx.cond(
                AuthState.error_message != "",
                rx.text(AuthState.error_message, color=FALSE_COLOR, weight="bold"),
            ),
            rx.input(
                placeholder="Email",
                value=AuthState.email,
                on_change=AuthState.set_email,
                width="100%",
                border_radius="0",
            ),
            rx.input(
                placeholder="Senha",
                type="password",
                value=AuthState.password,
                on_change=AuthState.set_password,
                width="100%",
                border_radius="0",
            ),
            rx.button("Entrar", on_click=AuthState.handle_login, width="100%", border_radius="0"),
            rx.divider(),
            google_oauth_provider(
                google_login(on_success=AuthState.handle_google_login),
            ),
            rx.link("Nao tem conta? Cadastre-se", href="/register"),
            spacing="4",
            align_items="start",
            **card_style(max_width="420px"),
        ),
        height="100vh",
        padding="1em",
        class_name=FORCE_LIGHT_CLASS,
    )
