"""Adapter 实现：唯一允许 import 第三方 SDK 的地方。

Day 1 只做 ping，够 /ready 用。真正的读写方法随 M0 逐个补。
"""

from __future__ import annotations

from typing import Any

import structlog
from minio import Minio
from pymilvus import MilvusClient
from sqlalchemy import create_engine, text

from .config import Settings
from .ports import StoredObject

log = structlog.get_logger(__name__)


class MinioObjectStore:
    def __init__(self, s: Settings) -> None:
        self._client = Minio(
            s.minio_endpoint,
            access_key=s.minio_root_user,
            secret_key=s.minio_root_password,
            secure=s.minio_secure,
        )
        self._bucket = s.minio_bucket_raw

    def ping(self) -> bool:
        try:
            exists = self._client.bucket_exists(self._bucket)
            if not exists:
                self._client.make_bucket(self._bucket)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("minio.ping_failed", error=str(e))
            return False

    def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        from io import BytesIO

        r = self._client.put_object(
            self._bucket, key, BytesIO(data), length=len(data), content_type=content_type
        )
        return StoredObject(key=key, size=len(data), etag=r.etag or "")

    def get(self, key: str) -> bytes:
        resp = self._client.get_object(self._bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception:  # noqa: BLE001
            return False

    def presign(self, key: str, ttl_s: int = 3600) -> str:
        from datetime import timedelta

        return self._client.presigned_get_object(self._bucket, key, expires=timedelta(seconds=ttl_s))


class MySqlMetaStore:
    def __init__(self, s: Settings) -> None:
        self._engine = create_engine(s.mysql_dsn, pool_pre_ping=True, pool_size=5)

    def ping(self) -> bool:
        try:
            with self._engine.connect() as c:
                c.execute(text("SELECT 1"))
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("mysql.ping_failed", error=str(e))
            return False

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._engine.begin() as c:
            rows = c.execute(text(sql), params or {})
            return [dict(r._mapping) for r in rows] if rows.returns_rows else []

    def close(self) -> None:
        self._engine.dispose()


class MilvusVectorStore:
    def __init__(self, s: Settings) -> None:
        self._client = MilvusClient(uri=s.milvus_uri)

    def ping(self) -> bool:
        try:
            self._client.list_collections()
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("milvus.ping_failed", error=str(e))
            return False
