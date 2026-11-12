# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

规则：每个**能跑**的版本才打 tag；每版在 `docs/releases/vX.Y.Z.md` 写六段详情（目标 / 做了什么 / 怎么验收 / 数据迁移 / 已知问题 / 下一步）。本文件只做索引，一行一条。

## [Unreleased]

### Added
- 仓库骨架：docker compose（minio / mysql / etcd / milvus / app）、配置、JSON 日志
- `src/ports.py` 五个协议：ObjectStore / MetaStore / VectorStore / LLMProvider / Embedder
- `src/adapters.py` 三个 ping 实现，`/health` 与 `/ready`
- 方案文档 `docs/plan.md`
- 数据模型：`source` / `block` / `note` 三表，`block.text` 建 ngram 全文索引（迁移 `0001`）
- `sha256` 唯一索引（迁移 `fab1d7318466`），防并发重复入库
- `src/ingest/store.py`：幂等入库 `store_source`，先存 MinIO 再写库，`IntegrityError` 回查兜底
- 进程级单例 `get_object_store()` / `get_vector_store()`
- 测试：`tests/test_store.py`（哈希稳定性、幂等、非法后缀），内容随机 + 用后清理，可重复跑

### Changed
- `MetaStore` 协议不再使用：MySQL 是自己的库，直接用 SQLAlchemy，不做无意义的抽象
- MySQL 宿主机端口改为 `3307`（本机已有 MySQL 服务占用 3306）
- MinIO 镜像改用 `milvusdb/minio`（官方镜像 2025 年停止分发同 tag）

### Docs
- `docs/progress.md`：进度与交接，换机器/换会话先读它
