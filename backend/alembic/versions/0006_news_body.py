"""news body

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("news", sa.Column("body", sa.Text(), server_default=sa.text("''"), nullable=False))
    # Existing briefings stored their full text in `summary`.
    op.execute("UPDATE news SET body = summary")


def downgrade() -> None:
    op.drop_column("news", "body")
