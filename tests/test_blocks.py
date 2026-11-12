import pytest
from sqlalchemy import delete

from src.db import session_scope
from src.ids import new_id
from src.ingest.blocks import list_orphaned, store_blocks, text_hash
from src.ingest.markdown import BlockDraft
from src.models import Block, Source


def _new_source() -> str:
    """造一条 source 当外键目标，sha256 用随机值避开唯一索引。"""
    source_id = new_id()
    with session_scope() as s:
        s.add(
            Source(
                id=source_id,
                kind="md",
                title="测试文档",
                object_key="test/key",
                sha256=new_id().lower().ljust(64, "0")[:64],
                size_bytes=1,
            )
        )
    return source_id


def _drop_source(source_id: str) -> None:
    with session_scope() as s:
        s.execute(delete(Block).where(Block.source_id == source_id))
        s.execute(delete(Source).where(Source.id == source_id))


def _drafts(count: int) -> list[BlockDraft]:
    return [
        BlockDraft(seq=i + 1, breadcrumb="测试文档 › 第1节", heading="第1节", text=f"段落 {i + 1}")
        for i in range(count)
    ]


def test_store_blocks_creates_and_orders() -> None:
    source_id = _new_source()
    try:
        with session_scope() as s:
            ids = store_blocks(_drafts(3), source_id, s)
        assert len(ids) == 3
        assert len(set(ids)) == 3

        with session_scope() as s:
            rows = s.query(Block).filter(Block.source_id == source_id).order_by(Block.seq).all()
        assert [r.text for r in rows] == ["段落 1", "段落 2", "段落 3"]
        assert rows[0].text_hash == text_hash("段落 1")
    finally:
        _drop_source(source_id)


def test_reparse_reuses_block_ids() -> None:
    """内容没变，id 必须不变——否则历史引用全断。"""
    source_id = _new_source()
    try:
        with session_scope() as s:
            first = store_blocks(_drafts(3), source_id, s)
        with session_scope() as s:
            again = store_blocks(_drafts(3), source_id, s)
        assert first == again

        with session_scope() as s:
            assert s.query(Block).filter(Block.source_id == source_id).count() == 3
    finally:
        _drop_source(source_id)


def test_unused_blocks_marked_orphaned() -> None:
    source_id = _new_source()
    try:
        with session_scope() as s:
            store_blocks(_drafts(3), source_id, s)
        with session_scope() as s:
            store_blocks(_drafts(2), source_id, s)  # 第三块这次没出现

        with session_scope() as s:
            orphans = list_orphaned(s, source_id)
        assert len(orphans) == 1
        assert orphans[0]["seq"] == 3
    finally:
        _drop_source(source_id)


def test_orphan_revives_when_content_returns() -> None:
    source_id = _new_source()
    try:
        with session_scope() as s:
            store_blocks(_drafts(2), source_id, s)
        with session_scope() as s:
            store_blocks(_drafts(1), source_id, s)
        with session_scope() as s:
            assert len(list_orphaned(s, source_id)) == 1

        with session_scope() as s:
            store_blocks(_drafts(2), source_id, s)
        with session_scope() as s:
            assert list_orphaned(s, source_id) == []
    finally:
        _drop_source(source_id)
