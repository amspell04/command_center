"""initial: tasks, notes, news

Revision ID: 0001
Revises:
Create Date: 2026-10-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_type = postgresql.ENUM("WORK", "PERSONAL", name="task_type", create_type=False)


def upgrade() -> None:
    task_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("type", task_type, nullable=False),
        sa.Column("requirement", sa.Text(), server_default="", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("date_created", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_due_date_completed", "tasks", ["due_date", "completed"])

    op.create_table(
        "notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("date_created", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_notes"),
    )

    op.create_table(
        "news",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("quiz_section", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("sources", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("date_created", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_news"),
    )
    op.create_index("ix_news_date_created", "news", ["date_created"])


def downgrade() -> None:
    op.drop_index("ix_news_date_created", table_name="news")
    op.drop_table("news")
    op.drop_table("notes")
    op.drop_index("ix_tasks_due_date_completed", table_name="tasks")
    op.drop_table("tasks")
    task_type.drop(op.get_bind(), checkfirst=True)
