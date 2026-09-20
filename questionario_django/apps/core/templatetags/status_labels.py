"""Porte de frontend/questionario/style.py::STATUS_LABELS/status_label."""

from django import template

register = template.Library()

STATUS_LABELS = {
    "pending": "Pendente",
    "accepted": "Aceito",
    "rejected": "Rejeitado",
    "active": "Ativa",
    "reported": "Reportada",
    "removed": "Removida",
}

CHIP_KIND = {
    "accepted": "true",
    "active": "true",
    "rejected": "neutral",
    "removed": "false",
    "pending": "accent",
    "reported": "accent",
}


@register.filter
def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


@register.filter
def status_chip_kind(status: str) -> str:
    return CHIP_KIND.get(status, "neutral")
