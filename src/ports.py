"""Port 定义：业务代码只认这些协议，永远不 import 具体 SDK。

换 Milvus、换 MinIO、换 MySQL 时，只改 src/adapters.py，这里不动。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    etag: str


@dataclass(frozen=True)
class VectorRow:
    id: str
    vector: list[float]
    owner_id: str = "single"
    source_id: str = ""
    doc_type: str = ""
    note_id: str = ""


@dataclass(frozen=True)
class Hit:
    id: str
    score: float
    payload: dict[str, Any]


@runtime_checkable
class ObjectStore(Protocol):
    """原始文件。永不修改，只新增；key 由内容 sha256 决定。"""

    def ping(self) -> bool: ...
    def put(self, key: str, data: bytes, content_type: str) -> StoredObject: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def presign(self, key: str, ttl_s: int = 3600) -> str: ...


@runtime_checkable
class MetaStore(Protocol):
    """元数据与正文。幂等写入、事务边界、强制 owner 过滤都在实现里。"""

    def ping(self) -> bool: ...
    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


@runtime_checkable
class VectorStore(Protocol):
    """向量。纯派生数据，可整库删除后重建，因此不进备份。"""

    def ping(self) -> bool: ...
    def upsert(self, collection: str, rows: list[VectorRow]) -> int: ...
    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        expr: str | None = None,
    ) -> list[Hit]: ...
    def drop(self, collection: str) -> None: ...


@runtime_checkable
class LLMProvider(Protocol):
    """生成。所有调用走这里，便于统一重试、限流、换供应商。"""

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        json_mode: bool = False,
    ) -> str: ...


@runtime_checkable
class Embedder(Protocol):
    """向量化。bge-m3 为 1024 维，换模型要同步改 collection schema。"""

    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
