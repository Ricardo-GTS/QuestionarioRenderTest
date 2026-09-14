import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState
from questionario.state.question_state import QuestionState
from questionario.style import (
    FORCE_LIGHT_CLASS,
    SQUARE_BUTTON_SHAPE,
    TRUE_COLOR,
    card_style,
    square_button_color_props,
)


def home_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Criar pergunta Verdadeiro/Falso", size="7"),
                rx.text(
                    "Se ja existir uma pergunta parecida no banco, a gente te mostra em vez de duplicar.",
                    color="var(--gray-11)",
                ),
                rx.cond(
                    QuestionState.success_message != "",
                    rx.text(QuestionState.success_message, color=TRUE_COLOR, weight="bold"),
                ),
                rx.cond(
                    QuestionState.error_message != "",
                    rx.vstack(
                        rx.text(QuestionState.error_message, weight="bold"),
                        rx.text("Ja existe uma pergunta parecida com essa:", size="2", color="var(--gray-11)"),
                        rx.foreach(
                            QuestionState.similar_questions,
                            lambda match: rx.box(rx.text(match["statement"]), **card_style(padding="0.75em")),
                        ),
                        spacing="2",
                        width="100%",
                    ),
                ),
                rx.text_area(
                    placeholder="Enunciado da pergunta",
                    value=QuestionState.statement,
                    on_change=QuestionState.set_statement,
                    width="100%",
                    border_radius="0",
                ),
                rx.input(
                    placeholder="Categoria (opcional)",
                    value=QuestionState.category,
                    on_change=QuestionState.set_category,
                    width="100%",
                    border_radius="0",
                ),
                rx.hstack(
                    rx.button(
                        "Verdadeiro",
                        on_click=QuestionState.set_correct_answer("true"),
                        **SQUARE_BUTTON_SHAPE,
                        **square_button_color_props(QuestionState.correct_answer == "true", "true"),
                    ),
                    rx.button(
                        "Falso",
                        on_click=QuestionState.set_correct_answer("false"),
                        **SQUARE_BUTTON_SHAPE,
                        **square_button_color_props(QuestionState.correct_answer == "false", "false"),
                    ),
                    spacing="3",
                ),
                rx.button(
                    "Criar pergunta",
                    on_click=QuestionState.handle_create_question,
                    width="100%",
                    border_radius="0",
                ),
                rx.link(
                    rx.button("Fazer Questionario", variant="soft", width="100%", border_radius="0"),
                    href="/quiz",
                ),
                spacing="4",
                align_items="start",
                width=["90%", "70%", "500px"],
                padding="1.5em",
            ),
        ),
        on_mount=AuthState.load_current_user,
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
