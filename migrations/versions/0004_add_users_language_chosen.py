"""Add users.language_chosen: whether the user has picked a language yet.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The constant default fills existing rows with false without rewriting the table,
    # so every existing user sees the language picker once.
    op.add_column(
        "users",
        sa.Column("language_chosen", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The flags are lost; upgrading again shows everyone the picker once more.
    op.drop_column("users", "language_chosen")
