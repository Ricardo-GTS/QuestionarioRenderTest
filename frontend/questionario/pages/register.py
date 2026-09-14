import reflex as rx
from reflex_google_auth import google_login, google_oauth_provider

from questionario.state.auth_state import AuthState
from questionario.style import FALSE_COLOR, FORCE_LIGHT_CLASS, card_style


def register_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Criar conta", size="7"),
            rx.text("Cadastre-se pra criar perguntas e responder o pool da turma.", color="var(--gray-11)"),
            rx.cond(
                AuthState.error_message != "",
                rx.text(AuthState.error_message, color=FALSE_COLOR, weight="bold"),
            ),
            rx.input(
                placeholder="Nome",
                value=AuthState.name,
                on_change=AuthState.set_name,
                width="100%",
                border_radius="0",
            ),
            rx.input(
                placeholder="Email",
                value=AuthState.email,
                on_change=AuthState.set_email,
                width="100%",
                border_radius="0",
            ),
            rx.input(
                placeholder="Senha (minimo 8 caracteres)",
                type="password",
                value=AuthState.password,
                on_change=AuthState.set_password,
                width="100%",
                border_radius="0",
            ),
            rx.button("Cadastrar", on_click=AuthState.handle_register, width="100%", border_radius="0"),
            rx.divider(),
            google_oauth_provider(
                google_login(on_success=AuthState.handle_google_login),
            ),
            rx.link("Ja tem conta? Entrar", href="/login"),
            spacing="4",
            align_items="start",
            **card_style(max_width="420px"),
        ),
        height="100vh",
        padding="1em",
        class_name=FORCE_LIGHT_CLASS,
    )
