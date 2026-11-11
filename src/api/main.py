"""API 层。Day 1 只有健康检查，业务路由随 M0 逐个加。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..adapters import MilvusVectorStore, MinioObjectStore, MySqlMetaStore
from ..config import get_settings
from ..logging import get_logger, setup_logging

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.object_store = MinioObjectStore(s)
    app.state.meta_store = MySqlMetaStore(s)
    app.state.vector_store = MilvusVectorStore(s)
    log.info("app.started", env=s.mysql_database)
    yield
    app.state.meta_store.close()
    log.info("app.stopped")


app = FastAPI(title="my-study", version="0.1.0.dev0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """存活探针：进程活着就算过，不碰依赖。"""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """就绪探针：三个依赖全通才算就绪。首页排障就看这个。"""
    checks = {
        "minio": app.state.object_store.ping(),
        "mysql": app.state.meta_store.ping(),
        "milvus": app.state.vector_store.ping(),
    }
    ok = all(checks.values())
    return JSONResponse(
        status_code=200 if ok else 503,
        content={"status": "ok" if ok else "degraded", "dependencies": checks},
    )
