"""ORM 模型：Source（L2 资料）/ Block（检索单位）/ Note（L1 笔记）。

字段顺序、类型、索引都不是随手写的，每处注释说明"为什么"。
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Source(Base):
    """L2 资料。原始文件不可变，换版本 = 新增一行 + 把旧行标 superseded。"""

    __tablename__ = "source"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID，时间有序
    owner_id: Mapped[str] = mapped_column(String(26), default="single")  # 鉴权留位
    kind: Mapped[str] = mapped_column(Enum("pdf", "md", "web", name="source_kind"))
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(200))

    object_key: Mapped[str] = mapped_column(String(300))  # MinIO key，内容寻址
    sha256: Mapped[str] = mapped_column(String(64), index=True)  # 幂等依据：同文件不重复解析
    size_bytes: Mapped[int] = mapped_column("bytes", BigInteger)  # 属性名避开内置 bytes
    lang: Mapped[str | None] = mapped_column(String(8))
    meta_json: Mapped[dict | None] = mapped_column(JSON)  # ISBN / 出版社 / 来源 URL 等不规则字段

    # 版本链：新版本指向被它取代的那一行，旧的只改状态不删除
    version_tag: Mapped[str | None] = mapped_column(String(50))
    supersedes_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("source.id"))
    status: Mapped[str] = mapped_column(
        Enum("active", "superseded", "archived", name="source_status"), default="active"
    )

    # 解析状态机：pending → parsed → ready / rejected
    parse_state: Mapped[str] = mapped_column(
        Enum("pending", "parsed", "ready", "rejected", name="parse_state"), default="pending"
    )
    parse_conf: Mapped[float | None] = mapped_column(Numeric(3, 2))  # 置信度低则等人工确认
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Block(Base):
    """文档切出来的一段，检索与引用的最小单位。图/表/公式共用这张表，靠 kind 区分。"""

    __tablename__ = "block"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(26), ForeignKey("source.id"))
    seq: Mapped[int] = mapped_column()  # 文档内顺序，用于判断相邻块合并

    # 图文混合留位：M0 只会写入 text
    kind: Mapped[str] = mapped_column(
        Enum("text", "figure", "table", "formula", name="block_kind"), default="text"
    )
    asset_key: Mapped[str | None] = mapped_column(String(300))  # 图在 MinIO 的 key
    caption: Mapped[str | None] = mapped_column(String(500))
    bbox_json: Mapped[dict | None] = mapped_column(JSON)  # 页内坐标，高亮定位用

    # 冗余存路径：embedding 要拼、引用要显示、出题要定位，三处高频读
    breadcrumb: Mapped[str] = mapped_column(String(500))
    heading: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))  # 重解析时判断要不要重算向量
    token_count: Mapped[int] = mapped_column(default=0)
    # 重解析时没被复用 → 打上时间戳；不删除，检索层用 IS NULL 过滤
    orphaned_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_block_source", "source_id", "seq"),
        Index("idx_block_hash", "text_hash"),
        Index("idx_block_orphaned", "orphaned_at"),
        # 中文必须 ngram；ngram_token_size 建索引时生效，改了要重建
        Index("ft_block_text", "text", mysql_prefix="FULLTEXT", mysql_with_parser="ngram"),
    )


class Note(Base):
    """L1 笔记。正文放 MySQL：要参与检索、要事务、单条才几 KB。"""

    __tablename__ = "note"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(26), default="single")
    title: Mapped[str] = mapped_column(String(500))
    body_md: Mapped[str] = mapped_column(Text)  # MySQL TEXT 上限 64KB，单条笔记足够

    # 学习信号：只有 confirmed=True 才算"学过"，才可出题
    origin: Mapped[str] = mapped_column(Enum("self", "ai", name="note_origin"), default="self")
    confirmed: Mapped[bool] = mapped_column(default=True)

    # 网页剪藏留位（v0.5）
    source_url: Mapped[str | None] = mapped_column(String(1000))
    clipped_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_note_confirmed", "confirmed", "created_at"),)
