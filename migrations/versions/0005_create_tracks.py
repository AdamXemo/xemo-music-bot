"""Create the tracks table: the file_id cache of tracks Telegram already holds.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27 16:11:38.794379
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tracks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_track_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("artist", sa.Text(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("tg_file_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("title <> ''", name=op.f("ck_tracks_title_not_empty")),
        sa.CheckConstraint("duration >= 0", name=op.f("ck_tracks_duration_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tracks")),
        sa.UniqueConstraint(
            "provider", "provider_track_id", name=op.f("uq_tracks_provider_provider_track_id")
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The cache is lost; every track is downloaded once more after upgrading again.
    op.drop_table("tracks")
