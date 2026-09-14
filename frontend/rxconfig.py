import reflex as rx

from questionario.style import APP_THEME

config = rx.Config(
    app_name="questionario",
    backend_host="0.0.0.0",
    # Em modo prod, o Reflex serve frontend e o backend interno (state/websocket)
    # na mesma porta em um unico processo -- por isso as duas precisam ser iguais.
    backend_port=3000,
    frontend_port=3000,
    plugins=[rx.plugins.RadixThemesPlugin(theme=APP_THEME), rx.plugins.SitemapPlugin()],
)
