import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.models import AdminQuestionItem, AdminReportItem
from questionario.state.admin_state import AdminModerationState
from questionario.state.auth_state import AuthState
from questionario.style import (
    FALSE_COLOR,
    FORCE_LIGHT_CLASS,
    TRUE_COLOR,
    card_style,
    status_label,
)


def _reporter_row(report: AdminReportItem) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(report["reporter_name"], weight="bold", size="2"),
            rx.cond(report["reason_category"], rx.badge(report["reason_category"], size="1")),
            spacing="2",
            align="center",
        ),
        rx.text(report["reason"], size="2", color="var(--gray-11)"),
        padding="0.5em 0",
        border_bottom="1px solid var(--gray-4)",
        width="100%",
    )


def _question_row(question: AdminQuestionItem) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(f"Pergunta criada por {question['author_name']}", size="2", color="var(--gray-11)"),
                rx.text(question["statement"], weight="bold"),
                rx.hstack(
                    rx.text("Resposta cadastrada:", size="2", color="var(--gray-11)"),
                    rx.text(
                        rx.cond(question["correct_answer"], "Verdadeiro", "Falso"),
                        size="2",
                        weight="bold",
                        color=rx.cond(question["correct_answer"], TRUE_COLOR, FALSE_COLOR),
                    ),
                    rx.text(status_label(question["status"]), size="2", color="var(--gray-11)"),
                    spacing="2",
                    align="center",
                ),
                align_items="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.button(
                    "Aprovar Remocao",
                    on_click=AdminModerationState.approve_removal(question["id"]),
                    size="2",
                    color_scheme="red",
                    border_radius="0",
                ),
                rx.button(
                    "Rejeitar Remocao",
                    on_click=AdminModerationState.reject_removal(question["id"]),
                    size="2",
                    border_radius="0",
                ),
                spacing="2",
            ),
            width="100%",
            align="start",
        ),
        rx.vstack(
            rx.text("Reportado por:", size="2", weight="bold"),
            rx.foreach(question["reports"], _reporter_row),
            spacing="1",
            align_items="start",
            width="100%",
            padding_top="0.5em",
            border_top="1px solid var(--gray-5)",
        ),
        **card_style(),
    )


def admin_moderation_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.vstack(
            rx.heading("Perguntas reportadas", size="7"),
            rx.text(
                "Aprovar Remocao remove a pergunta e aceita os reportes pendentes dela. "
                "Rejeitar Remocao mantem/reativa a pergunta e rejeita os reportes pendentes.",
                size="2",
                color="var(--gray-11)",
            ),
            rx.cond(
                AdminModerationState.error_message != "",
                rx.text(AdminModerationState.error_message, color=FALSE_COLOR, weight="bold"),
            ),
            rx.cond(
                AdminModerationState.success_message != "",
                rx.text(AdminModerationState.success_message, color=TRUE_COLOR, weight="bold"),
            ),
            rx.cond(
                AdminModerationState.loading,
                rx.text("Carregando..."),
                rx.cond(
                    AdminModerationState.questions,
                    rx.foreach(AdminModerationState.questions, _question_row),
                    rx.text("Nenhum reporte pendente no momento -- tudo em dia."),
                ),
            ),
            spacing="3",
            align_items="start",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminModerationState.load_reported],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
