import reflex as rx

from questionario.state.report_state import ReportState


def report_modal() -> rx.Component:
    return rx.cond(
        ReportState.show_modal,
        rx.box(
            rx.box(
                rx.vstack(
                    rx.heading("Reportar pergunta", size="4"),
                    rx.cond(
                        ReportState.error_message != "",
                        rx.text(ReportState.error_message, color="red"),
                    ),
                    rx.text_area(
                        placeholder="Descreva o motivo (ex: resposta incorreta, enunciado ambiguo...)",
                        value=ReportState.reason,
                        on_change=ReportState.set_reason,
                        width="100%",
                    ),
                    rx.input(
                        placeholder="Tipo de problema (opcional)",
                        value=ReportState.reason_category,
                        on_change=ReportState.set_reason_category,
                        width="100%",
                    ),
                    rx.hstack(
                        rx.button("Cancelar", on_click=ReportState.close_modal, variant="soft"),
                        rx.button("Enviar reporte", on_click=ReportState.submit_report),
                        spacing="3",
                    ),
                    spacing="3",
                ),
                background="white",
                padding="1.5em",
                border_radius="8px",
                max_width="420px",
                width="90%",
            ),
            position="fixed",
            top="0",
            left="0",
            width="100%",
            height="100%",
            background="rgba(0, 0, 0, 0.4)",
            display="flex",
            align_items="center",
            justify_content="center",
            z_index="1000",
        ),
    )
