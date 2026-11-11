from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete

from src.db import session_scope
from src.ingest.store import content_hash, store_source
from src.models import Block, Source


def _drop_source(source_id: str) -> None:
    """先删引用方（block），再删被引用方（source），否则外键报错。"""
    with session_scope() as s:
        s.execute(delete(Block).where(Block.source_id == source_id))
        s.execute(delete(Source).where(Source.id == source_id))


def test_content_hash_is_stable() -> None:
    assert content_hash(b"abc") == content_hash(b"abc")
    assert content_hash(b"abc") != content_hash(b"abd")


def test_store_source_is_idempotent(tmp_path: Path) -> None:
    # 内容带随机后缀：测试不依赖库当前状态，重复跑也不会被历史数据干扰
    f = tmp_path / "a.md"
    f.write_text(f"# 标题 {uuid4()}\n\n正文", encoding="utf-8")

    source_id: str | None = None
    try:
        id1, created1 = store_source(f)
        source_id = id1
        id2, created2 = store_source(f)

        assert created1 is True
        assert created2 is False
        assert id1 == id2
    finally:
        if source_id is not None:
            _drop_source(source_id)


def test_unsupported_suffix_is_rejected(tmp_path: Path) -> None:
    f = tmp_path / "a.exe"
    f.write_bytes(b"MZ")
    with pytest.raises(ValueError):
        store_source(f)
