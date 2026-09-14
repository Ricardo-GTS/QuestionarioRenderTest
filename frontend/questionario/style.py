"""Sistema de design do Questionario -- ver design.md.

Motivo central: o binario Verdadeiro/Falso como logica de cor do produto
inteiro, nao so nos botoes de resposta. Cantos retos ("cartao de prova"),
nao o card-com-sombra-suave genérico. Ver CLAUDE.md pra armadilhas do Reflex
que este arquivo ja contorna (rx.theme(color_mode=...) nao funciona em
sub-componente; radius="none" no tema do App resolve isso globalmente).
"""

import reflex as rx

# --- Paleta -----------------------------------------------------------------
# 6 papeis, nada de "fundo cream + acento terracota" nem "quase-preto + neon".
INK = "#16241C"  # texto/headings -- verde-tinta escuro, nao preto puro
PAPER = "#EFF3EE"  # fundo -- branco-salvia frio, nao cream
ACCENT = "#C88A1E"  # acao primaria + status "aguardando" (reported/pending)
TRUE_COLOR = "#2E7D5B"  # Verdadeiro / acerto / reporte aceito
FALSE_COLOR = "#B23A2E"  # Falso / erro / pergunta removida
BORDER = INK  # bordas dos "cartoes de prova" usam a propria tinta

# --- Tipografia ---------------------------------------------------------------
HEADING_FONT = "'Lora', serif"
BODY_FONT = "'IBM Plex Sans', sans-serif"

FONT_STYLESHEETS = [
    "https://fonts.googleapis.com/css2?"
    "family=Lora:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap",
]

# Estilo global do app (rx.App(style=GLOBAL_STYLE, ...)) -- define fonte/cor
# padrao pra rx.text/rx.heading/body sem precisar repetir em cada componente.
GLOBAL_STYLE = {
    "font_family": BODY_FONT,
    "background_color": PAPER,
    "color": INK,
    # respeita RNF de acessibilidade: reduz/corta animacao pra quem pediu.
    "@media (prefers-reduced-motion: reduce)": {
        "*": {"animation_duration": "0.01ms !important", "transition_duration": "0.01ms !important"},
    },
    rx.heading: {"font_family": HEADING_FONT, "color": INK},
    rx.text: {"font_family": BODY_FONT},
}


# --- Helpers reutilizaveis ----------------------------------------------------


def card_style(**overrides) -> dict:
    """"Cartao de prova": borda solida 2px, canto reto -- nao sombra+radius generico."""
    style = {
        "border": f"2px solid {BORDER}",
        "border_radius": "0",
        "padding": "1.25em",
        "background": "white",
        "width": "100%",
    }
    style.update(overrides)
    return style


def chip_style(kind: str, **overrides) -> dict:
    """Chip com contorno (nao pill preenchida) -- kind: true|false|accent|neutral."""
    color = {
        "true": TRUE_COLOR,
        "false": FALSE_COLOR,
        "accent": ACCENT,
        "neutral": "var(--gray-9)",
    }[kind]
    style = {
        "display": "inline-block",
        "border": f"1.5px solid {color}",
        "color": color,
        "border_radius": "0",
        "padding": "0.15em 0.6em",
        "font_size": "0.85em",
        "font_weight": "600",
        "background": "transparent",
    }
    style.update(overrides)
    return style


SQUARE_BUTTON_SHAPE = {
    "border_radius": "0",
    "min_width": "9em",
    "font_weight": "600",
}


STATUS_LABELS = {
    "pending": "Pendente",
    "accepted": "Aceito",
    "rejected": "Rejeitado",
    "active": "Ativa",
    "reported": "Reportada",
    "removed": "Removida",
}


def status_label(status) -> rx.Var:
    """Traduz o status (Var string) pro rotulo em portugues -- ver STATUS_LABELS."""
    label = rx.Var.create(status)
    for value, text in STATUS_LABELS.items():
        label = rx.cond(status == value, text, label)
    return label


def report_status_chip_props(status) -> dict:
    """Chip com contorno pro status de Report/Question -- `status` e' uma Var
    string ("pending"/"accepted"/"rejected"/"active"/"reported"/"removed")."""
    color = rx.cond(
        (status == "accepted") | (status == "active"),
        TRUE_COLOR,
        rx.cond((status == "rejected"), "var(--gray-9)", rx.cond(status == "removed", FALSE_COLOR, ACCENT)),
    )
    return {
        "border": f"1.5px solid {color}",
        "color": color,
        "display": "inline-block",
        "border_radius": "0",
        "padding": "0.15em 0.6em",
        "font_size": "0.85em",
        "font_weight": "600",
    }


def outcome_chip_props(is_true) -> dict:
    """Chip com contorno pro feedback certo/errado do quiz -- `is_true` e' uma Var."""
    return {
        "border": rx.cond(is_true, f"1.5px solid {TRUE_COLOR}", f"1.5px solid {FALSE_COLOR}"),
        "color": rx.cond(is_true, TRUE_COLOR, FALSE_COLOR),
        "display": "inline-block",
        "border_radius": "0",
        "padding": "0.15em 0.6em",
        "font_size": "0.85em",
        "font_weight": "600",
    }


def square_button_color_props(is_active, kind: str) -> dict:
    """Props dinamicas (via rx.cond, `is_active` e' uma Var) pro botao V/F:
    neutro em repouso, cor de estado so' quando selecionado. `kind`: "true"|"false".
    Combine com **SQUARE_BUTTON_SHAPE no mesmo rx.button pela forma quadrada.
    """
    color = TRUE_COLOR if kind == "true" else FALSE_COLOR
    return {
        "background": rx.cond(is_active, color, "transparent"),
        "color": rx.cond(is_active, "white", INK),
        "border": rx.cond(is_active, f"2px solid {color}", "2px solid var(--gray-7)"),
    }


APP_THEME = rx.theme(appearance="light", accent_color="amber", radius="none", scaling="100%")

# rx.theme(appearance=...) e' descartado na compilacao nesta versao do Reflex
# (0.9.10.post2), inclusive no APP_THEME acima (confirmado no JSX gerado) --
# entao o app inteiro segue o dark/light do SISTEMA do usuario por padrao, o
# que quebra qualquer cor fixa pensada pra um dos dois. Toda pagina aplica esta
# classe no seu componente raiz pra forcar claro sempre, independente do SO.
FORCE_LIGHT_CLASS = "radix-themes light light-theme"
