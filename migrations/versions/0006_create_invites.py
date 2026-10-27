"""Create the invites table: single-use invite codes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "invites",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("code ~ '^[A-Za-z0-9]{8}$'", name=op.f("ck_invites_code_format")),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_invites_expires_after_created")
        ),
        sa.CheckConstraint(
            "used_by IS NULL OR used_at IS NOT NULL",
            name=op.f("ck_invites_used_by_needs_used_at"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.tg_id"],
            name=op.f("fk_invites_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"],
            ["users.tg_id"],
            name=op.f("fk_invites_used_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_invites")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The invite history (who invited whom, which codes were used) is lost.
    op.drop_table("invites")
