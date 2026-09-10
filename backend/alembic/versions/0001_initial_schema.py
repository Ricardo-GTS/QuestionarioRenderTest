"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

question_status = sa.Enum("active", "reported", "removed", name="question_status")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Nao criar o enum manualmente aqui: op.create_table abaixo ja cria o tipo
    # "question_status" automaticamente ao criar a coluna dessa tabela.
    # Criar os dois causa "type already exists" dentro da mesma transacao.

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.Boolean(), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("status", question_status, nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_questions_status", "questions", ["status"])
    op.create_index(
        "ix_questions_embedding_hnsw",
        "questions",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("reason_category", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_index("ix_questions_embedding_hnsw", table_name="questions")
    op.drop_index("ix_questions_status", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    question_status.drop(op.get_bind(), checkfirst=True)
