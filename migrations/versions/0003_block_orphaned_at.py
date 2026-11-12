"""block.orphaned_at：重解析时没被复用的块，标记而不删除

Revision ID: 0003
Revises: fab1d7318466
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "fab1d7318466"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("block", sa.Column("orphaned_at", sa.DateTime(), nullable=True))
    op.create_index("idx_block_orphaned", "block", ["orphaned_at"])


def downgrade() -> None:
    op.drop_index("idx_block_orphaned", table_name="block")
    op.drop_column("block", "orphaned_at")
