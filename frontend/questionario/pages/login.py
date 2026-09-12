import reflex as rx
from reflex_google_auth import google_login, google_oauth_provider

from questionario.state.auth_state import AuthState


def login_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Entrar"),
            rx.cond(
                AuthState.error_message != "",
                rx.text(AuthState.error_message, color="red"),
            ),
            rx.input(
                placeholder="Email",
                value=AuthState.email,
                on_change=AuthState.set_email,
                width="100%",
            ),
            rx.input(
                placeholder="Senha",
                type="password",
                value=AuthState.password,
                on_change=AuthState.set_password,
                width="100%",
            ),
            rx.button("Entrar", on_click=AuthState.handle_login, width="100%"),
            rx.divider(),
            google_oauth_provider(
                google_login(on_success=AuthState.handle_google_login),
            ),
            rx.link("Nao tem conta? Cadastre-se", href="/register"),
            spacing="4",
            width=["90%", "70%", "400px"],
        ),
        height="100vh",
        padding="1em",
    )
