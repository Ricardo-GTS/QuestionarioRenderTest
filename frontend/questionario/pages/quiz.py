import reflex as rx

from questionario.components.navbar import navbar
from questionario.components.report_modal import report_modal
from questionario.state.auth_state import AuthState
from questionario.state.quiz_state import QuizState
from questionario.state.report_state import ReportState
from questionario.style import (
    FALSE_COLOR,
    FORCE_LIGHT_CLASS,
    SQUARE_BUTTON_SHAPE,
    TRUE_COLOR,
    card_style,
    outcome_chip_props,
    square_button_color_props,
)


def _feedback_item(item: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(item["statement"], weight="bold"),
                rx.box(
                    rx.cond(item["is_correct"], "Voce acertou", "Voce errou"),
                    **outcome_chip_props(item["is_correct"]),
                ),
                align_items="start",
                spacing="2",
            ),
            rx.spacer(),
            rx.button(
                "Reportar",
                on_click=ReportState.open_modal(item["question_id"]),
                variant="outline",
                size="2",
                border_radius="0",
            ),
            width="100%",
            align="start",
        ),
        **card_style(),
    )


def _quiz_result() -> rx.Component:
    return rx.vstack(
        rx.heading("Resultado", size="7"),
        rx.text(f"Pontuacao: {QuizState.score} / {QuizState.total}", size="6", weight="bold"),
        rx.foreach(QuizState.feedback, _feedback_item),
        rx.button(
            "Fazer outro questionario", on_click=QuizState.start_quiz, width="100%", border_radius="0"
        ),
        spacing="3",
        width="100%",
        align_items="start",
    )


def _quiz_question() -> rx.Component:
    return rx.vstack(
        rx.text(QuizState.progress_label, size="5", weight="bold", font_family="'Lora', serif"),
        rx.box(
            rx.text(QuizState.current_question["statement"], weight="bold", size="5"),
            **card_style(padding="2em"),
        ),
        rx.hstack(
            rx.button(
                "Verdadeiro",
                on_click=QuizState.answer_current(True),
                width="100%",
                height="4em",
                **SQUARE_BUTTON_SHAPE,
                **square_button_color_props(False, "true"),
                _hover={"background": TRUE_COLOR, "color": "white"},
            ),
            rx.button(
                "Falso",
                on_click=QuizState.answer_current(False),
                width="100%",
                height="4em",
                **SQUARE_BUTTON_SHAPE,
                **square_button_color_props(False, "false"),
                _hover={"background": FALSE_COLOR, "color": "white"},
            ),
            spacing="3",
            width="100%",
        ),
        spacing="4",
        width="100%",
        align_items="start",
    )


def quiz_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        report_modal(),
        rx.center(
            rx.vstack(
                rx.cond(
                    QuizState.error_message != "",
                    rx.text(QuizState.error_message, color=FALSE_COLOR, weight="bold"),
                ),
                rx.cond(
                    QuizState.loading,
                    rx.text("Carregando questionario..."),
                    rx.cond(
                        QuizState.submitted,
                        _quiz_result(),
                        rx.cond(
                            QuizState.questions,
                            _quiz_question(),
                            rx.vstack(
                                rx.heading("Sem perguntas pra responder ainda", size="5"),
                                rx.text(
                                    "Crie a primeira pergunta pra comecar o pool da turma.",
                                    color="var(--gray-11)",
                                ),
                                rx.link(rx.button("Criar Pergunta", border_radius="0"), href="/"),
                                spacing="3",
                                align_items="start",
                            ),
                        ),
                    ),
                ),
                spacing="4",
                width=["90%", "70%", "500px"],
                padding="1.5em",
                align_items="start",
            ),
        ),
        on_mount=[AuthState.load_current_user, QuizState.start_quiz],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
