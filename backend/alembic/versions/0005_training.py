"""training: goal target date, maxes, programs, sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PK_DEFAULT = sa.text("gen_random_uuid()")


def _lift() -> postgresql.ENUM:
    return postgresql.ENUM("SQUAT", "BENCH", "DEADLIFT", name="lift", create_type=False)


def upgrade() -> None:
    op.add_column("goals", sa.Column("target_date", sa.Date(), nullable=True))
    postgresql.ENUM("SQUAT", "BENCH", "DEADLIFT", name="lift").create(op.get_bind())

    op.create_table(
        "training_maxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=PK_DEFAULT, nullable=False),
        sa.Column("lift", _lift(), nullable=False),
        sa.Column("weight", sa.Numeric(6, 1), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_training_maxes"),
        sa.UniqueConstraint("lift", "effective_date", name="uq_training_maxes_lift_date"),
        sa.CheckConstraint("weight > 0", name="ck_training_maxes_weight"),
    )

    op.create_table(
        "programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=PK_DEFAULT, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("weeks", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_programs"),
        sa.CheckConstraint("weeks BETWEEN 1 AND 52", name="ck_programs_weeks"),
    )
    op.create_index("uq_programs_one_active", "programs", ["active"], unique=True, postgresql_where=sa.text("active"))

    op.create_table(
        "program_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=PK_DEFAULT, nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("lift", _lift(), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("percent", sa.Numeric(4, 1), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], name="fk_program_sets_program_id_programs", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_program_sets"),
        sa.CheckConstraint("week >= 1", name="ck_program_sets_week"),
        sa.CheckConstraint("day BETWEEN 1 AND 7", name="ck_program_sets_day"),
        sa.CheckConstraint("sets BETWEEN 1 AND 20", name="ck_program_sets_sets"),
        sa.CheckConstraint("reps BETWEEN 1 AND 30", name="ck_program_sets_reps"),
        sa.CheckConstraint("percent > 0 AND percent <= 150", name="ck_program_sets_percent"),
    )
    op.create_index("ix_program_sets_program_week_day", "program_sets", ["program_id", "week", "day"])

    op.create_table(
        "workout_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=PK_DEFAULT, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("bodyweight", sa.Numeric(5, 1), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_workout_sessions"),
        sa.UniqueConstraint("date", name="uq_workout_sessions_date"),
    )

    op.create_table(
        "lift_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=PK_DEFAULT, nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lift", _lift(), nullable=False),
        sa.Column("weight", sa.Numeric(6, 1), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("set_order", sa.Integer(), nullable=False),
        sa.Column("program_set_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["workout_sessions.id"], name="fk_lift_sets_session_id_workout_sessions", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_set_id"], ["program_sets.id"], name="fk_lift_sets_program_set_id_program_sets", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_lift_sets"),
        sa.CheckConstraint("weight > 0", name="ck_lift_sets_weight"),
        sa.CheckConstraint("reps BETWEEN 1 AND 30", name="ck_lift_sets_reps"),
    )
    op.create_index("ix_lift_sets_session_id", "lift_sets", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_lift_sets_session_id", table_name="lift_sets")
    op.drop_table("lift_sets")
    op.drop_table("workout_sessions")
    op.drop_index("ix_program_sets_program_week_day", table_name="program_sets")
    op.drop_table("program_sets")
    op.drop_index("uq_programs_one_active", table_name="programs")
    op.drop_table("programs")
    op.drop_table("training_maxes")
    postgresql.ENUM(name="lift").drop(op.get_bind())
    op.drop_column("goals", "target_date")
