import reflex as rx

from questionario.state.report_state import REASON_CATEGORIES, ReportState


def report_modal() -> rx.Component:
    return rx.cond(
        ReportState.show_modal,
        rx.box(
            # class_name forca as variaveis de CSS do tema claro do Radix (--gray-12
            # etc.) dentro do modal, nao importa o tema claro/escuro do navegador --
            # sem isso o texto (que segue o tema do navegador) fica ilegivel em cima
            # do "background=white" fixo abaixo, em modo escuro. rx.theme(color_mode=...)
            # nao funciona pra isso nesta versao do Reflex (0.9.10.post2): o prop de
            # aparencia nao chega a ser emitido no componente Theme compilado --
            # confirmado inspecionando o JSX gerado, entao aplicamos a classe direto.
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
                    rx.select(
                        REASON_CATEGORIES,
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
                class_name="radix-themes light light-theme",
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
