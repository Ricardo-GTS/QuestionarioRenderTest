import reflex as rx

from questionario.components.navbar import navbar
from questionario.components.report_modal import report_modal
from questionario.state.auth_state import AuthState
from questionario.state.quiz_state import QuizState
from questionario.state.report_state import ReportState


def _feedback_item(item: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.text(item["statement"], weight="bold"),
                rx.text(
                    rx.cond(item["is_correct"], "Voce acertou!", "Voce errou."),
                    color=rx.cond(item["is_correct"], "green", "red"),
                ),
                align_items="start",
                spacing="1",
            ),
            rx.spacer(),
            rx.button(
                "Reportar",
                on_click=ReportState.open_modal(item["question_id"]),
                variant="outline",
                size="2",
            ),
            width="100%",
        ),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        width="100%",
    )


def _quiz_result() -> rx.Component:
    return rx.vstack(
        rx.heading("Resultado"),
        rx.text(f"Pontuacao: {QuizState.score} / {QuizState.total}", size="5"),
        rx.foreach(QuizState.feedback, _feedback_item),
        rx.button("Fazer outro questionario", on_click=QuizState.start_quiz, width="100%"),
        spacing="3",
        width="100%",
    )


def _quiz_question() -> rx.Component:
    return rx.vstack(
        rx.text(QuizState.progress_label),
        rx.box(
            rx.text(QuizState.current_question["statement"], weight="bold", size="5"),
            padding="1.5em",
            border="1px solid #e2e2e2",
            border_radius="8px",
            width="100%",
        ),
        rx.hstack(
            rx.button("Verdadeiro", on_click=QuizState.answer_current(True), color_scheme="green", width="100%"),
            rx.button("Falso", on_click=QuizState.answer_current(False), color_scheme="red", width="100%"),
            spacing="3",
            width="100%",
        ),
        spacing="4",
        width="100%",
    )


def quiz_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        report_modal(),
        rx.center(
            rx.vstack(
                rx.cond(
                    QuizState.error_message != "",
                    rx.text(QuizState.error_message, color="red"),
                ),
                rx.cond(
                    QuizState.loading,
                    rx.text("Carregando questionario..."),
                    rx.cond(
                        QuizState.submitted,
                        _quiz_result(),
                        rx.cond(QuizState.questions, _quiz_question(), rx.box()),
                    ),
                ),
                spacing="4",
                width=["90%", "70%", "500px"],
                padding="1em",
            ),
        ),
        on_mount=[AuthState.load_current_user, QuizState.start_quiz],
        width="100%",
        spacing="0",
    )
