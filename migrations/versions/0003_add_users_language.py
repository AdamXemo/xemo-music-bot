"""Add users.language: the language the bot speaks to each user (ADR 0005).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-12 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # The constant default doubles as the backfill: Postgres 11+ fills existing rows
    # (config admins who already used the bot) with 'en' without rewriting the table.
    op.add_column("users", sa.Column("language", sa.Text(), server_default="en", nullable=False))
    # Literal SQL instead of the app's Language type: a migration must not change when
    # application code does.
    op.create_check_constraint(
        op.f("ck_users_language_valid"), "users", "language IN ('en', 'uk', 'ru')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Users' language choices are lost; upgrading again resets everyone to 'en'.
    op.drop_constraint(op.f("ck_users_language_valid"), "users", type_="check")
    op.drop_column("users", "language")
