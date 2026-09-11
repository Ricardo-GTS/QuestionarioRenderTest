import reflex as rx


def admin_nav() -> rx.Component:
    return rx.hstack(
        rx.link("Dashboard", href="/admin"),
        rx.link("Moderacao", href="/admin/moderation"),
        rx.link("Usuarios", href="/admin/users"),
        rx.link("Configuracoes", href="/admin/settings"),
        spacing="4",
        padding="1em",
        border_bottom="1px solid #e2e2e2",
        wrap="wrap",
    )
