import reflex as rx

from questionario.style import ACCENT, INK

CURRENT_PATH = rx.State.router.page.path


def _tab(label: str, href: str) -> rx.Component:
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


def admin_nav() -> rx.Component:
    return rx.hstack(
        _tab("Visao Geral", "/admin"),
        _tab("Moderacao", "/admin/moderation"),
        _tab("Perguntas Removidas", "/admin/removed"),
        _tab("Usuarios", "/admin/users"),
        _tab("Configuracoes", "/admin/settings"),
        spacing="5",
        padding="1em 1.5em",
        border_bottom=f"1px solid {INK}",
        wrap="wrap",
    )
