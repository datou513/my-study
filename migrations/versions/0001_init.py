"""init: source / block / note

Revision ID: 0001
Revises:
Create Date: 2026-11-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("owner_id", sa.String(26), nullable=False),
        sa.Column("kind", sa.Enum("pdf", "md", "web", name="source_kind"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("object_key", sa.String(300), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("lang", sa.String(8), nullable=True),
        sa.Column("meta_json", sa.JSON(), nullable=True),
        sa.Column("version_tag", sa.String(50), nullable=True),
        sa.Column("supersedes_id", sa.String(26), sa.ForeignKey("source.id"), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "superseded", "archived", name="source_status"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "parse_state",
            sa.Enum("pending", "parsed", "ready", "rejected", name="parse_state"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("parse_conf", sa.Numeric(3, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_source_sha256", "source", ["sha256"])

    op.create_table(
        "block",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("source_id", sa.String(26), sa.ForeignKey("source.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("text", "figure", "table", "formula", name="block_kind"),
            nullable=False,
            server_default="text",
        ),
        sa.Column("asset_key", sa.String(300), nullable=True),
        sa.Column("caption", sa.String(500), nullable=True),
        sa.Column("bbox_json", sa.JSON(), nullable=True),
        sa.Column("breadcrumb", sa.String(500), nullable=False),
        sa.Column("heading", sa.String(300), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("idx_block_source", "block", ["source_id", "seq"])
    op.create_index("idx_block_hash", "block", ["text_hash"])
    # 中文全文检索必须 ngram；ngram_token_size 在建索引时生效
    op.create_index(
        "ft_block_text", "block", ["text"], mysql_prefix="FULLTEXT", mysql_with_parser="ngram"
    )

    op.create_table(
        "note",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("owner_id", sa.String(26), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column(
            "origin", sa.Enum("self", "ai", name="note_origin"), nullable=False, server_default="self"
        ),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("clipped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("idx_note_confirmed", "note", ["confirmed", "created_at"])


def downgrade() -> None:
    op.drop_table("note")
    op.drop_index("ft_block_text", table_name="block")
    op.drop_index("idx_block_hash", table_name="block")
    op.drop_index("idx_block_source", table_name="block")
    op.drop_table("block")
    op.drop_index("ix_source_sha256", table_name="source")
    op.drop_table("source")
