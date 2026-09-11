"""admin panel: app_settings + quiz_attempts

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-11

"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Defaults iniciais -- os mesmos do .env.example. A partir daqui os valores
# efetivos ficam nesta tabela e sao editaveis via /admin/settings.
DEFAULT_SIMILARITY_THRESHOLD = 0.75
DEFAULT_QUIZ_SIZE = 10
DEFAULT_REPORT_THRESHOLD = 3


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("similarity_threshold", sa.Float(), nullable=False),
        sa.Column("quiz_size", sa.Integer(), nullable=False),
        sa.Column("report_threshold", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute(
        sa.text(
            "INSERT INTO app_settings (id, similarity_threshold, quiz_size, report_threshold) "
            "VALUES (1, :similarity_threshold, :quiz_size, :report_threshold)"
        ).bindparams(
            similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
            quiz_size=DEFAULT_QUIZ_SIZE,
            report_threshold=DEFAULT_REPORT_THRESHOLD,
        )
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_quiz_attempts_user_id", "quiz_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
    op.drop_table("app_settings")
