import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminUsersState
from questionario.state.auth_state import AuthState
from questionario.style import ACCENT, FALSE_COLOR, FORCE_LIGHT_CLASS, TRUE_COLOR, card_style


def _user_row(user: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.hstack(
                rx.text(user["name"], weight="bold"),
                rx.cond(user["is_admin"], rx.box("admin", border=f"1.5px solid {ACCENT}", color=ACCENT, padding="0.1em 0.5em", font_size="0.8em", font_weight="600")),
                spacing="2",
            ),
            rx.text(user["email"], size="2", color="var(--gray-11)"),
            rx.text(f"Perguntas criadas: {user['question_count']}", size="2", color="var(--gray-11)"),
            rx.hstack(
                rx.text(f"Reportes aceitos: {user['accepted_reports_count']}", size="2", color=TRUE_COLOR),
                rx.text(
                    f"Reportes rejeitados: {user['rejected_reports_count']}",
                    size="2",
                    color="var(--gray-11)",
                ),
                rx.text(
                    f"Perguntas removidas: {user['questions_removed_count']}",
                    size="2",
                    color=FALSE_COLOR,
                ),
                spacing="3",
                wrap="wrap",
            ),
            align_items="start",
            spacing="1",
        ),
        rx.spacer(),
        rx.cond(
            AdminUsersState.confirm_delete_id == user["id"],
            rx.hstack(
                rx.text("Confirmar exclusao?", color=FALSE_COLOR, weight="bold", size="2"),
                rx.button(
                    "Cancelar", on_click=AdminUsersState.cancel_delete, variant="soft", size="2",
                    border_radius="0",
                ),
                rx.button(
                    "Confirmar",
                    on_click=AdminUsersState.confirm_delete_user,
                    color_scheme="red",
                    size="2",
                    border_radius="0",
                ),
                spacing="2",
            ),
            rx.button(
                "Excluir",
                on_click=AdminUsersState.ask_delete(user["id"]),
                color_scheme="red",
                variant="outline",
                size="2",
                border_radius="0",
            ),
        ),
        **card_style(),
    )


def admin_users_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.vstack(
            rx.heading("Usuarios", size="7"),
            rx.cond(
                AdminUsersState.error_message != "",
                rx.text(AdminUsersState.error_message, color=FALSE_COLOR, weight="bold"),
            ),
            rx.cond(
                AdminUsersState.loading,
                rx.text("Carregando..."),
                rx.foreach(AdminUsersState.users, _user_row),
            ),
            spacing="3",
            align_items="start",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminUsersState.load_users],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
