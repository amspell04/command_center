"""goals

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("date_created", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_goals"),
    )


def downgrade() -> None:
    op.drop_table("goals")
