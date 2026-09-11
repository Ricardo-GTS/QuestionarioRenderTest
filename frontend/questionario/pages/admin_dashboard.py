import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminStatsState
from questionario.state.auth_state import AuthState


def _stat_box(label: str, value) -> rx.Component:
    return rx.box(
        rx.text(label, size="2", color="gray"),
        rx.text(value, size="6", weight="bold"),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        min_width="160px",
    )


def _category_row(item: dict) -> rx.Component:
    return rx.hstack(
        rx.text(item["category"]),
        rx.spacer(),
        rx.text(item["count"]),
        width="100%",
        padding_y="0.25em",
    )


def admin_dashboard_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.cond(
            AdminStatsState.error_message != "",
            rx.text(AdminStatsState.error_message, color="red", padding="1em"),
        ),
        rx.vstack(
            rx.heading("Visao geral"),
            rx.hstack(
                _stat_box("Usuarios", AdminStatsState.total_users),
                _stat_box("Perguntas ativas", AdminStatsState.total_questions_active),
                _stat_box("Perguntas reportadas", AdminStatsState.total_questions_reported),
                _stat_box("Perguntas removidas", AdminStatsState.total_questions_removed),
                wrap="wrap",
                spacing="3",
            ),
            rx.hstack(
                _stat_box("Total de reportes", AdminStatsState.total_reports),
                _stat_box("Tentativas de quiz", AdminStatsState.total_quiz_attempts),
                _stat_box(
                    "Taxa media de acerto",
                    rx.cond(
                        AdminStatsState.average_score_percent != None,  # noqa: E711
                        f"{AdminStatsState.average_score_percent}%",
                        "-",
                    ),
                ),
                wrap="wrap",
                spacing="3",
            ),
            rx.heading("Perguntas por categoria", size="4"),
            rx.foreach(AdminStatsState.questions_by_category, _category_row),
            rx.heading("Reportes por categoria", size="4"),
            rx.foreach(AdminStatsState.reports_by_category, _category_row),
            spacing="4",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminStatsState.load_stats],
        width="100%",
        spacing="0",
    )
