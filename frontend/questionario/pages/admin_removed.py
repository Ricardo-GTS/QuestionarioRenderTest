import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminRemovedState
from questionario.state.auth_state import AuthState
from questionario.style import (
    FALSE_COLOR,
    FORCE_LIGHT_CLASS,
    SQUARE_BUTTON_SHAPE,
    TRUE_COLOR,
    card_style,
    square_button_color_props,
)


def _edit_form() -> rx.Component:
    return rx.vstack(
        rx.text_area(
            value=AdminRemovedState.edit_statement,
            on_change=AdminRemovedState.set_edit_statement,
            width="100%",
            border_radius="0",
        ),
        rx.input(
            placeholder="Categoria",
            value=AdminRemovedState.edit_category,
            on_change=AdminRemovedState.set_edit_category,
            width="100%",
            border_radius="0",
        ),
        rx.hstack(
            rx.button(
                "Verdadeiro",
                on_click=AdminRemovedState.set_edit_correct_answer("true"),
                **SQUARE_BUTTON_SHAPE,
                **square_button_color_props(AdminRemovedState.edit_correct_answer == "true", "true"),
            ),
            rx.button(
                "Falso",
                on_click=AdminRemovedState.set_edit_correct_answer("false"),
                **SQUARE_BUTTON_SHAPE,
                **square_button_color_props(AdminRemovedState.edit_correct_answer == "false", "false"),
            ),
            spacing="3",
        ),
        rx.hstack(
            rx.button("Cancelar", on_click=AdminRemovedState.cancel_edit, variant="soft", border_radius="0"),
            rx.button("Salvar", on_click=AdminRemovedState.save_edit, border_radius="0"),
            spacing="3",
        ),
        spacing="3",
        **card_style(background="var(--gray-2)"),
    )


def _question_row(question: dict) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(question["statement"], weight="bold"),
                rx.text(
                    rx.cond(question["correct_answer"], "Resposta: Verdadeiro", "Resposta: Falso"),
                    size="2",
                    color="var(--gray-11)",
                ),
                align_items="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.vstack(
                rx.button(
                    "Reativar",
                    on_click=AdminRemovedState.reactivate(question["id"]),
                    size="2",
                    border_radius="0",
                ),
                rx.button(
                    "Editar",
                    on_click=AdminRemovedState.start_edit(question),
                    variant="soft",
                    size="2",
                    border_radius="0",
                ),
                spacing="2",
            ),
            width="100%",
            align="start",
        ),
        rx.cond(
            AdminRemovedState.editing_id == question["id"],
            _edit_form(),
        ),
        **card_style(),
    )


def admin_removed_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.vstack(
            rx.heading("Perguntas Removidas", size="7"),
            rx.text(
                "Reative uma pergunta removida por engano, ou edite antes de reativar.",
                size="2",
                color="var(--gray-11)",
            ),
            rx.cond(
                AdminRemovedState.error_message != "",
                rx.text(AdminRemovedState.error_message, color=FALSE_COLOR, weight="bold"),
            ),
            rx.cond(
                AdminRemovedState.success_message != "",
                rx.text(AdminRemovedState.success_message, color=TRUE_COLOR, weight="bold"),
            ),
            rx.cond(
                AdminRemovedState.loading,
                rx.text("Carregando..."),
                rx.cond(
                    AdminRemovedState.questions,
                    rx.foreach(AdminRemovedState.questions, _question_row),
                    rx.text("Nenhuma pergunta removida no momento."),
                ),
            ),
            spacing="3",
            align_items="start",
            padding="1.5em",
            width="100%",
            max_width="700px",
        ),
        on_mount=[AuthState.require_admin, AdminRemovedState.load_removed],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
