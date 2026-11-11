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
