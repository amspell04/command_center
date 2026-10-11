"""weak points

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weak_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("note_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("date_created", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.ForeignKeyConstraint(["note_id"], ["notes.id"], name="fk_weak_points_note_id_notes", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_weak_points"),
    )
    op.create_index("ix_weak_points_note_id", "weak_points", ["note_id"])
    op.create_index("uq_weak_points_note_topic", "weak_points", ["note_id", sa.text("lower(topic)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_weak_points_note_topic", table_name="weak_points")
    op.drop_index("ix_weak_points_note_id", table_name="weak_points")
    op.drop_table("weak_points")
