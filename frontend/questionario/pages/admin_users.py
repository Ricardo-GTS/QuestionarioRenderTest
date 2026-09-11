import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminUsersState
from questionario.state.auth_state import AuthState


def _user_row(user: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.text(user["name"], weight="bold"),
                rx.cond(user["is_admin"], rx.badge("admin")),
                spacing="2",
            ),
            rx.text(user["email"], size="2", color="gray"),
            rx.text(f"Perguntas criadas: {user['question_count']}", size="2", color="gray"),
            align_items="start",
            spacing="1",
        ),
        rx.spacer(),
        rx.cond(
            AdminUsersState.confirm_delete_id == user["id"],
            rx.hstack(
                rx.text("Confirmar exclusao?", color="red", size="2"),
                rx.button("Cancelar", on_click=AdminUsersState.cancel_delete, variant="soft", size="2"),
                rx.button(
                    "Confirmar",
                    on_click=AdminUsersState.confirm_delete_user,
                    color_scheme="red",
                    size="2",
                ),
                spacing="2",
            ),
            rx.button(
                "Excluir",
                on_click=AdminUsersState.ask_delete(user["id"]),
                color_scheme="red",
                variant="outline",
                size="2",
            ),
        ),
        width="100%",
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
    )


def admin_users_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.vstack(
            rx.heading("Usuarios"),
            rx.cond(
                AdminUsersState.error_message != "",
                rx.text(AdminUsersState.error_message, color="red"),
            ),
            rx.cond(
                AdminUsersState.loading,
                rx.text("Carregando..."),
                rx.foreach(AdminUsersState.users, _user_row),
            ),
            spacing="3",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminUsersState.load_users],
        width="100%",
        spacing="0",
    )
