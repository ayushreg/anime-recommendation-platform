"""Baseline schema revision.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-01
"""

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables are created by SQLAlchemy metadata on API boot.
    # This revision establishes Alembic history for future schema changes.
    op.execute("SELECT 1")


def downgrade() -> None:
    pass
