"""保存原始资料，并按文件内容去重（幂等）。"""

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.adapters import get_object_store
from src.db import session_scope
from src.ids import new_id
from src.models import Source

_FILE_TYPES = {
    ".pdf": ("pdf", "application/pdf"),
    ".md": ("md", "text/markdown"),
    ".markdown": ("md", "text/markdown"),
    ".html": ("web", "text/html"),
    ".htm": ("web", "text/html"),
}


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _detect(path: Path) -> tuple[str, str, str]:
    """返回 (kind, content_type, suffix)。不认识的后缀当场拒绝，别拖到解析时。"""
    suffix = path.suffix.lower()
    try:
        kind, content_type = _FILE_TYPES[suffix]
    except KeyError:
        raise ValueError(f"不支持的资料文件类型：{path.suffix}") from None
    return kind, content_type, suffix


def store_source(path: Path, title: str | None = None) -> tuple[str, bool]:
    """把文件收进库，返回 (source_id, created)。

    幂等：内容相同（sha256 相同）直接返回已有记录，created=False，不重复写。

    顺序是刻意的——先存对象存储、再写数据库。对象存储的写入可以重复执行，
    而"数据库里有记录、文件却没存上"是坏状态，解析时必然失败。
    """
    data = path.read_bytes()
    digest = content_hash(data)
    kind, content_type, suffix = _detect(path)

    # 只读查询：不需要 commit，用完立即归还连接
    with session_scope() as session:
        existing = session.scalar(select(Source.id).where(Source.sha256 == digest))
    if existing is not None:
        return existing, False

    key = f"{digest[:2]}/{digest}{suffix}"
    get_object_store().put(key, data, content_type)  # 事务外：网络 IO

    source_id = new_id()
    try:
        with session_scope() as session:  # 短事务：只做 insert
            session.add(
                Source(
                    id=source_id,
                    kind=kind,
                    title=title or path.stem,
                    object_key=key,
                    sha256=digest,
                    size_bytes=len(data),
                )
            )
    except IntegrityError:
        # 并发：另一个请求刚插入了同 sha256 的记录，回查它的 id
        with session_scope() as session:
            return session.scalar(select(Source.id).where(Source.sha256 == digest)), False

    return source_id, True
