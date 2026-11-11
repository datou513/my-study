"""unique source sha256

Revision ID: fab1d7318466
Revises: 0001
Create Date: 2026-11-11 11:51:25.268254

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'fab1d7318466'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_source_sha256", table_name="source")
    op.create_index("ix_source_sha256", "source", ["sha256"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_source_sha256", table_name="source")
    op.create_index("ix_source_sha256", "source", ["sha256"])