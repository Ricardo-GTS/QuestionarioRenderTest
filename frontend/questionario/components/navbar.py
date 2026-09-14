import reflex as rx

from questionario.state.auth_state import AuthState
from questionario.style import ACCENT, INK

CURRENT_PATH = rx.State.router.page.path


def _nav_link(label: str, href: str) -> rx.Component:
    is_active = CURRENT_PATH == href
    return rx.link(
        label,
        href=href,
        color=rx.cond(is_active, ACCENT, INK),
        border_bottom=rx.cond(is_active, f"2px solid {ACCENT}", "2px solid transparent"),
        padding_bottom="0.15em",
        weight=rx.cond(is_active, "bold", "regular"),
        _hover={"color": ACCENT},
    )


def navbar() -> rx.Component:
    return rx.hstack(
        rx.link(rx.heading("Questionario", size="5"), href="/"),
        rx.spacer(),
        rx.cond(
            AuthState.is_authenticated,
            rx.hstack(
                _nav_link("Criar Pergunta", "/"),
                _nav_link("Fazer Questionario", "/quiz"),
                _nav_link("Estatisticas", "/estatisticas"),
                _nav_link("Conta", "/account"),
                rx.cond(AuthState.is_admin, _nav_link("Admin", "/admin")),
                rx.button(
                    "Sair",
                    on_click=AuthState.logout,
                    size="2",
                    variant="outline",
                    border_radius="0",
                ),
                spacing="5",
                align="center",
            ),
            rx.hstack(
                _nav_link("Entrar", "/login"),
                _nav_link("Cadastrar", "/register"),
                spacing="5",
            ),
        ),
        width="100%",
        padding="1em 1.5em",
        border_bottom=f"2px solid {INK}",
        align="center",
        wrap="wrap",
    )
