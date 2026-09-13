import reflex as rx

from questionario.components.navbar import navbar
from questionario.state.auth_state import AuthState
from questionario.state.stats_state import StatsState


def _stat_box(label: str, value, color: str = "gray") -> rx.Component:
    return rx.box(
        rx.text(label, size="2", color="gray"),
        rx.text(value, size="6", weight="bold", color=color),
        padding="1em",
        border="1px solid #e2e2e2",
        border_radius="8px",
        min_width="220px",
    )


def estatisticas_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        rx.center(
            rx.vstack(
                rx.heading("Minhas estatisticas"),
                rx.cond(
                    StatsState.error_message != "",
                    rx.text(StatsState.error_message, color="red"),
                ),
                rx.cond(
                    StatsState.loading,
                    rx.text("Carregando..."),
                    rx.hstack(
                        _stat_box("Reportes aceitos", StatsState.accepted_reports_count, color="green"),
                        _stat_box("Reportes rejeitados", StatsState.rejected_reports_count),
                        _stat_box(
                            "Perguntas removidas por reporte",
                            StatsState.questions_removed_count,
                            color="red",
                        ),
                        wrap="wrap",
                        spacing="3",
                    ),
                ),
                rx.text(
                    "Reportes aceitos: reportes seus que o admin confirmou como validos. "
                    "Perguntas removidas: perguntas suas que foram reportadas e removidas pelo admin.",
                    size="2",
                    color="gray",
                ),
                spacing="4",
                padding="1.5em",
                width=["90%", "70%", "700px"],
            ),
        ),
        on_mount=[AuthState.load_current_user, StatsState.load_stats],
        width="100%",
        spacing="0",
    )
