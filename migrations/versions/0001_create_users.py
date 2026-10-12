"""Create the users table.

Revision ID: 0001
Revises:
Create Date: 2026-10-12 13:13:28.456473
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        sa.Column("tg_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default="user", nullable=False),
        sa.Column("invited_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin', 'user', 'blocked')", name=op.f("ck_users_role_valid")
        ),
        sa.CheckConstraint("invited_by <> tg_id", name=op.f("ck_users_not_self_invited")),
        sa.CheckConstraint("tg_id > 0", name=op.f("ck_users_tg_id_positive")),
        sa.ForeignKeyConstraint(
            ["invited_by"],
            ["users.tg_id"],
            name=op.f("fk_users_invited_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("tg_id", name=op.f("pk_users")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("users")
