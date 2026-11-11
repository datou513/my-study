# my-study

个人知识库：把资料（PDF / 笔记）变成可被考核的断言，再用考核结果告诉你薄弱项在哪。

- 方案与全部设计决策：[docs/plan.md](docs/plan.md)
- 踩坑记录：[docs/mistakes.md](docs/mistakes.md)
- 版本变更：[CHANGELOG.md](CHANGELOG.md)

## 快速开始

```bash
cp .env.example .env      # 改掉里面的密码
docker compose up -d      # 五个容器：minio / mysql / etcd / milvus / app
curl http://localhost:8000/ready
```

`/ready` 返回 `{"status":"ok","dependencies":{...}}` 才算环境就绪；任一依赖 false 就看对应容器日志。

## 目录

```
src/
  config.py      配置（pydantic-settings，从 .env 读）
  logging.py     JSON 日志
  ports.py       ★ 五个协议：业务只认接口，不认 SDK
  adapters.py    ★ 唯一 import 第三方 SDK 的地方
  api/main.py    /health 存活、/ready 就绪
  ingest/        解析与切块（M0 Day 3 开始）
  retrieval/     混合检索（M0 Day 5）
  answer/        问答与引用校验（M0 Day 6）
scripts/         备份 / 恢复
docs/            方案、ADR、发版说明、踩坑
```

## 本机开发（不用容器跑 app）

```bash
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload
```

依赖仍是容器里的 minio/mysql/milvus，`.env` 里的 host 用 `localhost`。
