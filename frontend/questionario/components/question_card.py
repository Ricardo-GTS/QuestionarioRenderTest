import reflex as rx


def question_card(statement: str, category: str | None = None) -> rx.Component:
    return rx.box(
        rx.text(statement, weight="bold"),
        rx.cond(
            category,
            rx.badge(category),
        ),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        width="100%",
    )
