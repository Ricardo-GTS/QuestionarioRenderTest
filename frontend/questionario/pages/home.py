import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState
from questionario.state.question_state import QuestionState


def home_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Criar pergunta Verdadeiro/Falso"),
                rx.cond(
                    QuestionState.success_message != "",
                    rx.text(QuestionState.success_message, color="green"),
                ),
                rx.cond(
                    QuestionState.error_message != "",
                    rx.vstack(
                        rx.text(QuestionState.error_message, color="red"),
                        rx.foreach(
                            QuestionState.similar_questions,
                            lambda match: rx.box(
                                rx.text(match["statement"]),
                                padding="0.5em",
                                border="1px solid #e2e2e2",
                                border_radius="6px",
                                width="100%",
                            ),
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
                ),
                rx.input(
                    placeholder="Categoria (opcional)",
                    value=QuestionState.category,
                    on_change=QuestionState.set_category,
                    width="100%",
                ),
                rx.hstack(
                    rx.button(
                        "Verdadeiro",
                        on_click=QuestionState.set_correct_answer("true"),
                        color_scheme=rx.cond(QuestionState.correct_answer == "true", "green", "gray"),
                    ),
                    rx.button(
                        "Falso",
                        on_click=QuestionState.set_correct_answer("false"),
                        color_scheme=rx.cond(QuestionState.correct_answer == "false", "red", "gray"),
                    ),
                    spacing="3",
                ),
                rx.button("Criar pergunta", on_click=QuestionState.handle_create_question, width="100%"),
                rx.link(rx.button("Responder questionario", variant="soft", width="100%"), href="/quiz"),
                spacing="4",
                width=["90%", "70%", "500px"],
                padding="1em",
            ),
        ),
        on_mount=AuthState.load_current_user,
        width="100%",
        spacing="0",
    )
