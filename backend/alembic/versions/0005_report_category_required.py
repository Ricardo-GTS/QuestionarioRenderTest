"""reportes: tipo de problema (reason_category) obrigatorio, motivo livre opcional

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-14

"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reportes antigos podem ter reason_category nulo (era opcional) -- backfill
    # antes de tornar a coluna obrigatoria, senao a constraint falha.
    op.execute("UPDATE reports SET reason_category = 'Outro' WHERE reason_category IS NULL")
    op.alter_column("reports", "reason_category", existing_type=sa.String(60), nullable=False)
    op.alter_column("reports", "reason", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE reports SET reason = '' WHERE reason IS NULL")
    op.alter_column("reports", "reason", existing_type=sa.Text(), nullable=False)
    op.alter_column("reports", "reason_category", existing_type=sa.String(60), nullable=True)
