"""把切好的块写进 block 表。

核心是重解析时的 id 复用：内容没变的块沿用旧 id，
这样 concept / attempt / 问答引用指向的 block.id 不会因为重切而失效。
"""

from hashlib import sha256

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.ids import new_id
from src.logging import get_logger
from src.models import Block

log = get_logger(__name__)


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def store_blocks(blocks, source_id: str, session: Session) -> list[str]:
    """写入一批块，返回与入参等长、同序的 block id 列表。

    - 内容相同（text_hash 命中旧块）→ 复用旧 id，并清掉 orphaned_at
    - 命中不了的旧块 → 标 orphaned_at（不删，历史引用还在）
    - 没有对应旧块的新块 → 新建

    session 由调用方传入：所有块要在同一个事务里，不能半本书入库。
    """
    old_rows = session.execute(
        select(Block.id, Block.text_hash).where(Block.source_id == source_id)
    ).all()
    old_by_hash: dict[str, str] = {h: i for i, h in old_rows}

    ids: list[str] = []
    reused: set[str] = set()
    to_insert: list[Block] = []

    for draft in blocks:
        h = text_hash(draft.text)
        old_id = old_by_hash.get(h)

        # `old_id not in reused`：同一文档里出现两次完全相同的段落时，
        # 只让第一个复用旧行，第二个照常新建，避免两行指向同一个 id。
        if old_id is not None and old_id not in reused:
            reused.add(old_id)
            ids.append(old_id)
            continue

        block_id = new_id()
        ids.append(block_id)
        to_insert.append(
            Block(
                id=block_id,
                source_id=source_id,
                seq=draft.seq,
                kind=draft.kind,
                breadcrumb=draft.breadcrumb,
                heading=draft.heading,
                text=draft.text,
                text_hash=h,
                token_count=len(draft.text),
            )
        )

    # 复活的块：内容回来了，不再算孤儿
    if reused:
        session.execute(
            update(Block)
            .where(Block.id.in_(reused), Block.orphaned_at.is_not(None))
            .values(orphaned_at=None)
        )

    # 被丢下的旧块：标记但不删除，检索层负责过滤
    orphan_ids = [bid for bid, _ in old_rows if bid not in reused]
    if orphan_ids:
        session.execute(
            update(Block)
            .where(Block.id.in_(orphan_ids), Block.orphaned_at.is_(None))
            .values(orphaned_at=func.now())
        )
        log.warning(
            "blocks.orphaned",
            source_id=source_id,
            count=len(orphan_ids),
            ids=orphan_ids[:5],
            hint="这些块不再被本次解析复用；检索时会过滤掉，但数据仍在",
        )

    if to_insert:
        session.add_all(to_insert)
    session.flush()
    return ids


def list_orphaned(session: Session, source_id: str | None = None) -> list[dict]:
    """列出被丢下的块。orphaned_at 不为空就会一直出现在这里，直到被清理。"""
    stmt = select(
        Block.id, Block.source_id, Block.seq, Block.breadcrumb, Block.orphaned_at
    ).where(Block.orphaned_at.is_not(None))
    if source_id is not None:
        stmt = stmt.where(Block.source_id == source_id)
    return [dict(row._mapping) for row in session.execute(stmt).all()]
