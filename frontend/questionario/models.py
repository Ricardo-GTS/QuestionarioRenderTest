"""Modelos tipados pra state -- TypedDict (nao dict puro, nao rx.PropsBase).

rx.foreach so' aninha corretamente sobre uma var de tipo concreto -- dict puro
nao tem tipo concreto o suficiente (ver CLAUDE.md). rx.PropsBase tem tipo
concreto e compila certo, mas so' serializa direito como DEFAULT ESTATICO da
classe -- atribuido dinamicamente num event handler (o caso real aqui), o
delta mandado pro navegador carrega o objeto Python cru em vez dos campos,
e tudo aparece como "undefined" na tela (bug real, ja caimos nele uma vez).
TypedDict e' um dict de verdade em runtime (serializa normal) com tipo
concreto o suficiente pro rx.foreach aninhar -- ver CLAUDE.md.
"""

from typing import TypedDict


class AdminReportItem(TypedDict):
    id: int
    reporter_name: str
    reason: str
    reason_category: str


class AdminQuestionItem(TypedDict):
    id: int
    author_name: str
    statement: str
    correct_answer: bool
    category: str
    status: str
    reports: list[AdminReportItem]


def question_item_from_api(data: dict) -> AdminQuestionItem:
    return AdminQuestionItem(
        id=data["id"],
        author_name=data["author_name"],
        statement=data["statement"],
        correct_answer=data["correct_answer"],
        category=data["category"] or "",
        status=data["status"],
        reports=[
            AdminReportItem(
                id=r["id"],
                reporter_name=r["reporter_name"],
                reason=r["reason"],
                reason_category=r["reason_category"] or "",
            )
            for r in data["reports"]
        ],
    )
