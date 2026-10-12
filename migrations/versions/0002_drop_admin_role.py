"""Drop the admin role: admin rights come only from ADMIN_IDS in config.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Safety net for development databases: no code ever wrote 'admin', and the new
    # CHECK would refuse to be created while such a row exists.
    op.execute("UPDATE users SET role = 'user' WHERE role = 'admin'")
    # op.f marks the names as final, so the naming convention is not applied twice.
    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role_valid"), "users", "role IN ('user', 'blocked')")


def downgrade() -> None:
    """Downgrade schema."""
    # The data rewrite is not reversed: which rows were 'admin' is not recorded.
    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_role_valid"), "users", "role IN ('admin', 'user', 'blocked')"
    )
