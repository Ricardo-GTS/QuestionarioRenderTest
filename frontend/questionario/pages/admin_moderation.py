import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminModerationState
from questionario.state.auth_state import AuthState


def _edit_form() -> rx.Component:
    return rx.vstack(
        rx.text_area(
            value=AdminModerationState.edit_statement,
            on_change=AdminModerationState.set_edit_statement,
            width="100%",
        ),
        rx.input(
            placeholder="Categoria",
            value=AdminModerationState.edit_category,
            on_change=AdminModerationState.set_edit_category,
            width="100%",
        ),
        rx.hstack(
            rx.button(
                "Verdadeiro",
                on_click=AdminModerationState.set_edit_correct_answer("true"),
                color_scheme=rx.cond(AdminModerationState.edit_correct_answer == "true", "green", "gray"),
            ),
            rx.button(
                "Falso",
                on_click=AdminModerationState.set_edit_correct_answer("false"),
                color_scheme=rx.cond(AdminModerationState.edit_correct_answer == "false", "red", "gray"),
            ),
            spacing="3",
        ),
        rx.hstack(
            rx.button("Cancelar", on_click=AdminModerationState.cancel_edit, variant="soft"),
            rx.button("Salvar", on_click=AdminModerationState.save_edit),
            spacing="3",
        ),
        spacing="3",
        width="100%",
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
    )


def _report_row(report: dict) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.text(report["question_statement"], size="2", color="gray"),
            rx.text(f"{report['reporter_name']}: {report['reason']}", weight="bold"),
            rx.cond(report["reason_category"], rx.badge(report["reason_category"])),
            rx.hstack(
                rx.badge(report["status"]),
                rx.spacer(),
                rx.button(
                    "Aceitar",
                    on_click=AdminModerationState.accept_report(report["id"]),
                    size="1",
                    color_scheme="green",
                ),
                rx.button(
                    "Rejeitar",
                    on_click=AdminModerationState.reject_report(report["id"]),
                    size="1",
                    color_scheme="red",
                    variant="soft",
                ),
                width="100%",
                align="center",
                spacing="2",
            ),
            align_items="start",
            spacing="2",
            width="100%",
        ),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        width="100%",
    )


def _question_row(question: dict) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(question["statement"], weight="bold"),
                rx.text(f"Reportes: {question['report_count']}", size="2", color="gray"),
                align_items="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.button("Aprovar", on_click=AdminModerationState.approve(question["id"]), size="2"),
                rx.button(
                    "Remover",
                    on_click=AdminModerationState.remove(question["id"]),
                    color_scheme="red",
                    size="2",
                ),
                rx.button(
                    "Editar",
                    on_click=AdminModerationState.start_edit(question),
                    variant="soft",
                    size="2",
                ),
                spacing="2",
            ),
            width="100%",
        ),
        rx.cond(
            AdminModerationState.editing_id == question["id"],
            _edit_form(),
        ),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        width="100%",
    )


def admin_moderation_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.vstack(
            rx.heading("Perguntas reportadas"),
            rx.cond(
                AdminModerationState.error_message != "",
                rx.text(AdminModerationState.error_message, color="red"),
            ),
            rx.cond(
                AdminModerationState.success_message != "",
                rx.text(AdminModerationState.success_message, color="green"),
            ),
            rx.cond(
                AdminModerationState.loading,
                rx.text("Carregando..."),
                rx.cond(
                    AdminModerationState.questions,
                    rx.foreach(AdminModerationState.questions, _question_row),
                    rx.text("Nenhuma pergunta reportada no momento."),
                ),
            ),
            rx.heading("Reportes individuais", size="4"),
            rx.text(
                "Aceitar/Rejeitar um reporte e' independente de Aprovar/Remover a pergunta acima.",
                size="2",
                color="gray",
            ),
            rx.cond(
                AdminModerationState.reports,
                rx.foreach(AdminModerationState.reports, _report_row),
                rx.text("Nenhum reporte no momento."),
            ),
            spacing="3",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminModerationState.load_reported],
        width="100%",
        spacing="0",
    )
