"""Add wider_clubs: named stubs for career-history employers outside the league.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 19:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the wider_clubs table."""
    op.create_table(
        "wider_clubs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("rev", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(), nullable=False),
        sa.Column("data", sa.Text(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop the wider_clubs table."""
    op.drop_table("wider_clubs")
