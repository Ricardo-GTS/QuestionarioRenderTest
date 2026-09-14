import reflex as rx

from questionario.components.admin_nav import admin_nav
from questionario.components.navbar import navbar
from questionario.state.admin_state import AdminSettingsState
from questionario.state.auth_state import AuthState
from questionario.style import FALSE_COLOR, FORCE_LIGHT_CLASS, TRUE_COLOR


def admin_settings_page() -> rx.Component:
    return rx.vstack(
        navbar(),
        admin_nav(),
        rx.center(
            rx.vstack(
                rx.heading("Configuracoes", size="7"),
                rx.cond(
                    AdminSettingsState.error_message != "",
                    rx.text(AdminSettingsState.error_message, color=FALSE_COLOR, weight="bold"),
                ),
                rx.cond(
                    AdminSettingsState.success_message != "",
                    rx.text(AdminSettingsState.success_message, color=TRUE_COLOR, weight="bold"),
                ),
                rx.text("Limiar de similaridade (0 a 1, ex: 0.75)", size="2", color="var(--gray-11)"),
                rx.input(
                    value=AdminSettingsState.similarity_threshold,
                    on_change=AdminSettingsState.set_similarity_threshold,
                    width="100%",
                    border_radius="0",
                ),
                rx.text("Tamanho do questionario (numero de perguntas)", size="2", color="var(--gray-11)"),
                rx.input(
                    value=AdminSettingsState.quiz_size,
                    on_change=AdminSettingsState.set_quiz_size,
                    width="100%",
                    border_radius="0",
                ),
                rx.text("Limiar de reportes para flagar uma pergunta", size="2", color="var(--gray-11)"),
                rx.input(
                    value=AdminSettingsState.report_threshold,
                    on_change=AdminSettingsState.set_report_threshold,
                    width="100%",
                    border_radius="0",
                ),
                rx.button("Salvar", on_click=AdminSettingsState.save_settings, width="100%", border_radius="0"),
                spacing="3",
                align_items="start",
                width=["90%", "70%", "400px"],
                padding="1.5em",
            ),
        ),
        on_mount=[AuthState.require_admin, AdminSettingsState.load_settings],
        width="100%",
        spacing="0",
        class_name=FORCE_LIGHT_CLASS,
    )
