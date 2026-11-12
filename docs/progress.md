# 进度与交接

> 换电脑、换会话、隔几周回来，先读这份 + `docs/plan.md`，就能接上。
> 这份文件只记"到哪了"，设计与理由在 `plan.md`，踩坑在 `mistakes.md`。

最后更新：2026-11-11（Day 3 完成）

---

## 一句话状态

环境跑通了，三张表建好了，能把一个文件幂等地收进库。**下一步是解析切块。**

---

## 已完成

### Day 1 · 环境（2026-11-10）

- `docker compose` 五服务：`minio` / `mysql` / `etcd` / `milvus` / `app`
- `GET /health`（存活）、`GET /ready`（minio + mysql + milvus 三项探活）
- `src/ports.py` 五个协议、`src/adapters.py` 三个实现、`src/config.py`、JSON 日志
- 首次提交已推到 GitHub `main`

**当前环境事实**：MySQL 宿主机端口是 **3307**（3306 被本机 MySQL 服务占用）；MinIO 用 `milvusdb/minio` 镜像（官方镜像下架）。

### Day 2 · 数据模型（2026-11-11）

- 三张表：`source`（L2 资料）/ `block`（检索单位）/ `note`（L1 笔记）
- `FULLTEXT ... WITH PARSER ngram` 建在 `block.text` 上（中文词法召回的地基）
- 迁移两个：`0001_init`（建表）、`fab1d7318466`（sha256 唯一索引）
- `block` 预留 `kind` / `asset_key` / `caption` / `bbox_json`（图文混合留位）

### Day 3 · 幂等入库（2026-11-11）

- `src/ingest/store.py`：`content_hash` / `store_source`
- 幂等：同 sha256 直接返回旧 id，`created=False`
- 顺序：**先存 MinIO，再写库**（对象写入可重放，坏状态只会是孤儿对象）
- 并发兜底：唯一索引 + `IntegrityError` 回查
- 进程级单例：`get_object_store()` / `get_vector_store()`（`lru_cache`）
- 测试：`tests/test_store.py` 三个用例，内容随机 + 用完删除，可重复跑

---

## 关键决策（详见 plan.md）

| # | 决策 |
| --- | --- |
| 1 | 定位是学习闭环，不是仓库：L2 资料 → L1 知识 → 断言 → 出题 → 归因 |
| 2 | 学过 = 有 `confirmed` 笔记，不设学习状态字段 |
| 3 | 知识点 = 一句可判真假的断言；知识点持久，题目易耗 |
| 4 | 判分用逐条 rubric（0/1/2），分数才可比；单次错只标"待观察" |
| 5 | 系统被动，不推送；但每次用完必须给诊断 |
| 6 | 查分定位/问答/摸底三动作；先内后外，来源分级 |
| 7 | 外部答案默认不存，收录必须过手改写才能进 L1 |
| 8 | 摄取先做文字版 PDF + Markdown；图文与多格式后置 |
| 9 | 技术栈 MinIO + MySQL + Milvus（练手目标，不追求最少组件） |
| 10 | 数据与系统分离：删掉 Milvus/MySQL 也要能从原文重建 |

---

## 待办

### Day 4（下一个）· Markdown 解析切块

三个判断先想清楚再写代码：

1. 标题层级 → `breadcrumb`（`书名 › 章 › 节`）
2. 多长算一块：按段落合并？按字数上限？
3. 代码块单独成块，还是并进上下文

### 之后

- Day 5 嵌入 + Milvus upsert + 全文检索（三路召回的第一、二路）
- Day 6 `/ask` 打通：召回 → 生成 → **引用校验**（虚引用必须丢弃）
- M0 验收：3 本书 + 50 篇笔记、20 条评测问题（库内 8/10、库外拒答 10/10）、删库重建

---

## 怎么恢复现场

```powershell
git clone https://github.com/datou513/my-study.git D:\my-study
cd D:\my-study
Copy-Item .env.example .env      # 填回密码（密码在密码管理器，不在仓库里）
docker compose up -d             # 空库也能起
./scripts/restore.sh <备份目录>   # 有备份才需要
docker compose exec app alembic upgrade head
docker compose exec app python -m pytest -q
curl.exe http://localhost:8000/ready
```

新会话开场说一句就行：

> 读 `docs/plan.md` 和 `docs/progress.md`，我们继续 Day N。

**上下文存在仓库里，不存在聊天窗口里。**
