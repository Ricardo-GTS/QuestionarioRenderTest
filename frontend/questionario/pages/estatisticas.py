import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState
from questionario.state.stats_state import StatsState
from questionario.style import FALSE_COLOR, FORCE_LIGHT_CLASS, TRUE_COLOR, card_style


def _stat_box(label: str, value, color: str = "var(--gray-11)") -> rx.Component:
    return rx.box(
        rx.text(label, size="2", color="var(--gray-11)"),
        rx.text(value, size="7", weight="bold", color=color, font_family="'Lora', serif"),
        **card_style(min_width="220px", width="auto"),
    )


def estatisticas_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Minhas estatisticas", size="7"),
                rx.cond(
                    StatsState.error_message != "",
                    rx.text(StatsState.error_message, color=FALSE_COLOR, weight="bold"),
                ),
                rx.cond(
                    StatsState.loading,
                    rx.text("Carregando..."),
                    rx.hstack(
                        _stat_box("Reportes aceitos", StatsState.accepted_reports_count, color=TRUE_COLOR),
                        _stat_box(
                            "Reportes rejeitados", StatsState.rejected_reports_count, color="var(--gray-11)"
                        ),
                        _stat_box(
                            "Perguntas removidas por reporte",
                            StatsState.questions_removed_count,
                            color=FALSE_COLOR,
                        ),
                        wrap="wrap",
                        spacing="3",
                    ),
                ),
                rx.text(
                    "Reportes aceitos: reportes seus que o admin confirmou como validos. "
                    "Perguntas removidas: perguntas suas que foram reportadas e removidas pelo admin.",
                    size="2",
                    color="var(--gray-11)",
                ),
                spacing="4",
                align_items="start",
                padding="1.5em",
                width=["90%", "70%", "700px"],
            ),
        ),
        on_mount=[AuthState.load_current_user, StatsState.load_stats],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
