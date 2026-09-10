import reflex as rx

from questionario.state.auth_state import AuthState


def register_page() -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Criar conta"),
            rx.cond(
                AuthState.error_message != "",
                rx.text(AuthState.error_message, color="red"),
            ),
            rx.input(
                placeholder="Nome",
                value=AuthState.name,
                on_change=AuthState.set_name,
                width="100%",
            ),
            rx.input(
                placeholder="Email",
                value=AuthState.email,
                on_change=AuthState.set_email,
                width="100%",
            ),
            rx.input(
                placeholder="Senha (minimo 8 caracteres)",
                type="password",
                value=AuthState.password,
                on_change=AuthState.set_password,
                width="100%",
            ),
            rx.button("Cadastrar", on_click=AuthState.handle_register, width="100%"),
            rx.link("Ja tem conta? Entrar", href="/login"),
            spacing="4",
            width=["90%", "70%", "400px"],
        ),
        height="100vh",
        padding="1em",
    )
