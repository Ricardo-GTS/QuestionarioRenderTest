"""reportes: veredito individual (accept/reject) + 1 reporte por usuario/pergunta

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

report_status_enum = sa.Enum("pending", "accepted", "rejected", name="report_status")


def upgrade() -> None:
    report_status_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "reports",
        sa.Column("status", report_status_enum, nullable=False, server_default="pending"),
    )
    op.alter_column("reports", "status", server_default=None)

    # Bancos que ja existiam antes dessa regra podem ter o mesmo usuario
    # reportando a mesma pergunta mais de uma vez -- a constraint unica abaixo
    # falharia nesses casos. Mantem so' o reporte mais recente de cada par
    # question_id+reporter_id e descarta os demais antes de criar a constraint.
    op.execute(
        "DELETE FROM reports WHERE id NOT IN "
        "(SELECT MAX(id) FROM reports GROUP BY question_id, reporter_id)"
    )
    op.create_unique_constraint("uq_reports_question_reporter", "reports", ["question_id", "reporter_id"])


def downgrade() -> None:
    op.drop_constraint("uq_reports_question_reporter", "reports", type_="unique")
    op.drop_column("reports", "status")
    report_status_enum.drop(op.get_bind(), checkfirst=True)
