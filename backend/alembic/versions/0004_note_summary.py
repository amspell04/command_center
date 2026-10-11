"""note summary

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notes", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("notes", sa.Column("summary_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notes", sa.Column("summary_source_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("notes", "summary_source_hash")
    op.drop_column("notes", "summary_generated_at")
    op.drop_column("notes", "summary")
