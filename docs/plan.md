# 个人知识库 · 产品与技术方案 v1.0

- 日期：2026-11-10
- 仓库：https://github.com/datou513/my-study.git（本地：`D:\my-study`）
- 状态：待评审。本方案基于前 17 轮讨论的共识，凡与此前草案冲突处，以此文为准。

---

## 0. 这份方案怎么读

第 1–3 章是**产品**（做什么、为什么），第 4–6 章是**实现**（怎么搭、存什么），第 7–9 章是**执行**（做到哪、怎么验收、怎么管版本）。

如果你只想看结论：**第 7 章的范围表 + 第 8 章的验收标准**。

---

## 1. 定位

### 1.1 一句话

> 一个把「别人的资料」转化为「你自己的知识」的系统：资料必须经你改写才能入库，入库的每一条断言都可被考核，考核结果告诉你薄弱项在哪。

它不是仓库，是一条流水线。存储只是中间产物。

### 1.2 核心闭环

```
L2 资料（PDF / 书）
      │  阅读
      ▼
L1 知识（你写的 / 你确认过的笔记）
      │  抽取
      ▼
断言（一条可判真假的陈述）── 按主题归组
      │  出题（记忆 / 理解 / 应用）
      ▼
作答 ──▶ 逐条 rubric 判分 ──▶ 分数 + 原因 + 解析
      │
      ▼
诊断（哪个主题、哪条断言、错在哪种题型）
      │
      └──▶ 回到 L2 补读，或回到 L1 重写
```

### 1.3 三个非目标

1. **不做编辑器军备竞赛**。Markdown 编辑够用即可，不追 WYSIWYG、块引用、数据库视图。
2. **不做主动学习系统**。不推送、不排复习计划、不判定「你今天该学什么」。系统只在你发起后给结论。
3. **不做多人实时协作**。v1 是单用户使用，但**鉴权会作为独立迭代版本实现**（见 7.6）——既是为了迟早要暴露到公网，也是刻意的学习目标。

### 1.4 双目标的处理

这个项目同时是「技术练手」和「长期在用的知识库」。两者对架构的要求相反，本方案的解法是：

| | 长期持有 | 可随时推倒 |
| --- | --- | --- |
| 内容 | MinIO 里的原始文件、`mysqldump` 导出、Markdown 导出 | Milvus collection、索引、缓存 |
| 依据 | 原始文件永不修改 | 一切派生数据都可从原文重算 |

**验收线：删掉 Milvus 和 MySQL 全部数据，只留 MinIO 原始文件 + 一份元数据导出，能一条命令重建可用库。**

---

## 2. 概念模型

### 2.1 两层知识

| 层 | 装什么 | 谁写的 | 用途 |
| --- | --- | --- | --- |
| **L2 资料** | 书、PDF、网页快照 | 别人 | 只读、只引用、只查证 |
| **L1 知识** | 你的笔记、总结、断言 | 你（或你确认的 AI 草稿） | 默认可信、可检索、可出题 |

**分层理由：**
- 书会淹没笔记。检索时若不区分，召回会被"别人的原文"稀释。
- 出题必须考 L1。考 L2 是考"读没读过"，不是"懂没懂"。
- L2 可随时重灌、换格式、搬存储；L1 永远是你的资产。

### 2.2 实体关系

```
Source（L2 资料）
  └─ Block（块，自包含，带 breadcrumb）
        │
        │  阅读 / 引用
        ▼
Note（L1 笔记：手写 or AI 草稿）
  ├─ origin: self | ai
  ├─ confirmed: bool          ← 只有 true 才算"学过"
  └─ 引用若干 Block（出处）
        │
        │  懒抽取
        ▼
Concept（断言：一句可判真假的陈述）
  ├─ topic（主题，可归组）
  └─ 持久：抽一次就固定，可合并 / 退役
        │
        ├──▶ Question（题目：瞬时生成，可收藏）
        │        └─ rubric（2–4 条评分要点，逐条 0/1/2）
        │
        └──▶ Attempt（作答记录：分数、逐条判定、错因）
                 └─ 驱动薄弱项诊断
```

### 2.3 五条硬规则

1. **学过 = 有 `confirmed` 笔记。** 不引入"未读/在读/已学"状态字段——那东西维护三天就会放弃。有笔记就是学过。
2. **知识点是断言，不是名词。** `BM25` 无法出题；`BM25 依赖词项统计，因此对同义改写不敏感` 可以。断言是最小判分单位，按主题归组。
3. **知识点持久，题目易耗。** Concept 抽一次固化（几百个量级），Question 每次重新生成（不维护题库）。唯一例外是用户主动收藏的题。
4. **引用锚点是 `block_id`，不是页码或字符偏移。** 换解析器、重切块后，页码全变，块 ID 不变。答案的"点回原文"半年后要还能用。
5. **外部内容不入 L1。** GPT / DeepSeek / 豆包的答案只能以 L2 身份入库，且必须经你改写才能升级为 L1。

---

## 3. 关键机制

### 3.1 摄取（v1：文字版 PDF + Markdown）

**统一中间层**，四层各自可重建：

```
原始文件（MinIO，永不修改）
    ↓ 解析
规范化文档树（章节层级 + 段落块，稳定 block_id）   ← 可重建
    ↓
块（自包含检索单位）
    ↓
向量 + 全文索引                                ← 可重建
```

**PDF 必须处理掉四件事：**

1. 页眉页脚与页码——按"每页重复出现的行"识别剔除，不用固定坐标。
2. 跨页断段与断词——`informa-` / `tion` 要在同页内先接回，再判断跨页合并。
3. 双栏——先判栏数，按栏切再按阅读顺序拼接，否则得到左右串行乱句。
4. 章节识别——优先编号（`3.2`），其次字号/加粗，兜底"按页组"并标低置信度。

**默认剔除：** 版权页、目录页、参考文献、索引页。这些对问答和出题都是纯噪声。支持"只入第 3–8 章"的范围选择。

**切分策略按来源分：**

| 来源 | 依据 | 块大小 | 附加 |
| --- | --- | --- | --- |
| PDF / 书 | 章 → 节 | 500–800 字 | 块文本前缀拼 `书名 › 章 › 节` 再算 embedding |
| Markdown 笔记 | 标题层级 | 300–600 字 | 保留原始 frontmatter |

**入库验收（硬门槛）：** 解析完立刻出预览——章节树、块数量、前 5 块原文。置信度低（字符提取率异常、块长度分布异常）标黄，人工确认后才进检索。

**断言懒抽取：** Markdown 导入时只做结构化，不抽断言。第一次考某篇笔记、或第一次拿它回答问题时，才抽那篇。避免一次性对几千篇笔记跑 LLM。

**断点续跑：** 每块处理完记录状态，嵌入批处理中断可从断点继续（本地 CPU 跑 bge-m3 时尤其需要）。

### 3.2 检索

三个动作，三种产物形态，不要合并成一个搜索框。

| 动作 | 场景 | 产物 | 是否用 LLM |
| --- | --- | --- | --- |
| **定位** | "我记得写过权重那段" | 片段列表 + 出处 + 上下文两行 | 不用 |
| **问答** | "纯 BM25 为什么不够" | 答案 + 逐句引用 + 拒答 | 用 |
| **摸底** | "RAG 切分我到底知道什么" | 断言清单 + 矛盾提示 + 空白提示 | 用（聚合） |

**混合检索三路：**

```
query ─┬─▶ MySQL FULLTEXT（ngram 分词）      → 词法候选
       ├─▶ Milvus ANN（COSINE, HNSW）        → 语义候选
       └─▶ MySQL 结构化过滤（时间/来源/类型） → 收窄范围

   融合（RRF 或加权）→ 相邻块合并去重 → top-k
```

排序初值：`0.45·词法 + 0.35·语义 + 0.10·时效 + 0.10·图邻近`，权重进配置，用评测集校准后再调。

**融合用 RRF** 而不是分数加权更省事：两路分数不同量纲，RRF 只看排名，不用归一化。

### 3.3 问答（先内后外）

**路由：**

| 库内情况 | 行为 |
| --- | --- |
| 够用 | 只用库，逐句带 `block_id` 引用 |
| 有部分 | 分段：库内部分（带引用）+ 外部补充（灰底标记） |
| 没有 | 外部回答，明确提示"这不在你的库里"；或直接拒答（取决于配置） |

**来源分级，永远可见：**

| 标记 | 含义 | 可信度 |
| --- | --- | --- |
| `L1` | 你确认过的断言 / 笔记 | 最高 |
| `L2` | 资料原文 | 高，未消化 |
| `外部` | 模型记忆 / 联网结果 | 未知，需核实 |

**引用校验（防幻觉的关键一步）：** 模型返回的引用必须逐个核对——引用的 `block_id` 是否真的在本次上下文里。不在的直接丢弃，并把该句标记为"无据"。这一步做的不是锦上添花，**没有它，用户用两次就会开始怀疑全部答案。**

**外部答案处理：** 默认不存。答完问一句"收录吗"。收录时：
- AI 答案放侧栏参考，**不进正文**；
- 正文由你从空白（或骨架）写起；
- 例外：纯事实型信息（版本号、API 名、日期）可存为"资料条目"（L2，带链接和抓取日期），不必改写。

### 3.4 出题与判分

**题目分类（决定 rubric 写法和判分可靠性）：**

| 类型 | 考什么 | 判分方式 | 可靠性 |
| --- | --- | --- | --- |
| 记忆 recall | 事实、定义、数值 | 要点比对 | 高 |
| 理解 explain | 为什么、怎么运作 | rubric 逐条判定 | 中高 |
| 应用 apply | 换场景、举例、找反例 | rubric 逐条判定 | 中 |
| 综合 synthesize | 跨笔记比较、立论 | **不判分**，改用写作 + 逐条挑毛病 | — |

**生成时机：即时生成，用完即弃。** 不做预生成题库——笔记一改，题库全废。

**一次考核的流程：**

```
选范围（最近两周 / 这一章 / 上次错的）
  → 取 Concept，按配比出题（如 5 记忆 / 2 理解 / 1 应用）
  → 逐题作答
  → 逐条 rubric 判定（0 未达成 / 1 部分 / 2 达成）
  → 分数 = 得分/满分，附未达成条目的原因 + 固定解析 + 出处
  → 本次报告
  → 询问：这几道值得留下吗？→ 冻结成收藏题
```

**分数可比的前提是 rubric 固定。** 出题时一次性生成题干、参考答案、rubric、解析并锁定；判分只做"逐条对照"，不做"整体印象给个 7 分"。同一答案判两次、换模型判，都应该接近。判分温度设 0。

**安全阀：**
- 单次答错 → 标 `pending`（待观察），不判薄弱。
- 同一 Concept 第二次错（且分数 < 60%）→ 升为 `weak`（确认薄弱）。
- 你可以标"这题出得不好" → 该 Attempt 记 `invalid`，不计入统计。

### 3.5 诊断与错题本

**四层判断：**

| 层 | 看什么 | 产出 |
| --- | --- | --- |
| 断言 | 哪条 Concept 没拿下 | 最小修补单位 |
| 主题 | 主题下薄弱断言占比 ≥ 40% | "整块没学扎实" |
| 错因 | 失分发生在哪类题型 | 记不住 / 理解偏 / 用不出 |
| 稳定性 | 出错次数与时间分布 | 偶发 or 反复 |

**报告示例：**

```
本次 8 题（5 记忆 / 2 理解 / 1 应用），涉及 11 条断言、3 个主题

混合检索（5 条）  4 掌握 / 1 模糊
  · BM25 对同义改写不敏感        记忆型错 1 次 → 待观察

切分策略（4 条）  2 掌握 / 2 未掌握
  · 按标题切 vs 按语义切的权衡    理解型错 2 次 → 确认薄弱
    证据：两次都选了"语义切分更便宜"，但笔记写的是"更贵但更准"
    建议：回读《切分策略》第 3 节

综合：本次最该补的是「切分策略」，不是分数最低的那题。
```

**错题本**是系统被动姿态下的唯一回顾入口：按主题聚合，显示错了几次、上次何时、错因、一键重考。

---

## 4. 架构

### 4.1 边界划分

按**外部依赖**切边界，不按技术分层。四个业务边界 + 三个 port。

```
┌──────────────────────────────────────────────────┐
│  api（FastAPI）/ cli                              │
├──────────────────────────────────────────────────┤
│  ingest      retrieval     answer      quiz       │
│  解析切块     混合检索       问答引用     断言出题判分  │
├──────────────────────────────────────────────────┤
│  ports（接口，只有协议定义）                        │
│    ObjectStore      MetaStore      VectorStore     │
│    LLMProvider      Embedder                       │
├──────────────────────────────────────────────────┤
│  adapters（唯一依赖具体组件的地方）                  │
│    MinIO            MySQL          Milvus          │
│    OpenAI 兼容 / 豆包  bge-m3                      │
└──────────────────────────────────────────────────┘
```

**为什么这样切：** 换向量库只改一个 adapter（练手自由）；搬去 NAS 只改 adapter 的 endpoint（长期可用）；面试可讲"外部依赖收敛为 3 个 port"。

**但不要过度分层。** 不建 domain 实体层、不搞 repository 泛型、一个项目五个边界封顶。个人项目照搬整洁架构，最后会写出二十个空接口。

### 4.2 存储分工

| 组件 | 存什么 | 是否备份 |
| --- | --- | --- |
| **MinIO** | 原始 PDF / MD、解析中间产物 | 是（`mc mirror`） |
| **MySQL** | 元数据、块文本、笔记正文、断言、题目、作答 | 是（`mysqldump`） |
| **Milvus** | 块向量 | **不备份**（纯派生，可重算） |

Milvus 不备份是刻意取舍：备份一个随时能重算的东西，等于给运维加一道没有收益的手续。

**Milvus 与业务共用一个 MinIO 实例**（不同 bucket：`kb-raw` / `kb-milvus`），少一个容器。

### 4.3 三条数据流

**导入：**

```
上传 → 落 MinIO（key = sha256）
     → MySQL 建 source 记录（状态 pending）
     → 解析（Worker）→ 章节树 → 块 → MySQL block
     → 预览确认（置信度低则等待人工）
     → 嵌入（批处理，断点续跑）→ Milvus upsert
     → 状态 ready
```

**问答：**

```
query → 过滤条件解析（可选，LLM 抽 JSON 而非写 SQL）
     → 三路召回 → 融合 → 合并去重 → top-k
     → 拼上下文（breadcrumb + block_id + 来源标记）
     → LLM 生成（要求逐句引用 / 无据拒答）
     → 引用校验（丢弃虚引用，标记无据句）
     → 返回
```

**出题：**

```
选范围 → 取/抽 Concept → 按配比选题 → 生成题干+答案+rubric+解析（一次性锁定）
      → 作答 → 逐条判定 → Attempt 落库 → 诊断聚合 → 报告
```

### 4.4 降级策略

这是"你每天在用"的最低要求，不是过度设计：

| 故障 | 降级 |
| --- | --- |
| Milvus 不可用 | 退化为 MySQL 全文检索（召回下降，仍可用） |
| LLM 超时/不可用 | 只返回检索结果，不硬等 |
| 嵌入服务未就绪 | 新文档入队等待，不阻塞已有问答 |
| MinIO 不可用 | 只读模式（已有块文本在 MySQL，可答不可导） |

### 4.5 部署

```
云服务器 4C8G / 100GB（起步）
  docker compose:
    minio       :9000  桶 kb-raw, kb-milvus
    mysql       :3306  ngram 分词
    etcd        :2379  （Milvus 依赖）
    milvus      :19530 standalone
    app         :8000  FastAPI
    embed       :8010  bge-m3（CPU，可选独立容器）
```

**迁移到 NAS：** 全部状态在一个 `volumes/` 目录 + 一份 `dump.sql`。`rsync` + `docker compose up` 即可。**不使用任何云厂商托管服务**（RDS / OSS / 托管向量库），否则搬不动。

---

## 5. 数据模型

### 5.1 MySQL

只列关键字段，完整 DDL 在 M0 第一周产出。

```sql
-- 版本管理（每个迁移文件一条记录）
schema_version(version varchar(20) pk, applied_at datetime)

-- L2 资料
source(
  id            char(26) pk,          -- ULID
  owner_id      char(26) default 'single',  -- 鉴权留位，v0.6 换真实用户
  kind          enum('pdf','md','web'),
  title         varchar(500),
  author        varchar(200) null,
  object_key    varchar(300),         -- MinIO key
  sha256        char(64),             -- 幂等依据
  bytes         bigint,
  lang          char(8),
  meta_json     json,                 -- 出版社/ISBN/页数/来源URL…
  parse_state   enum('pending','parsed','ready','rejected'),
  parse_conf    decimal(3,2),         -- 解析置信度
  created_at    datetime
)

-- 块（检索与引用的最小单位）
block(
  id            char(26) pk,
  source_id     char(26),
  seq           int,
  kind          enum('text','figure','table','formula') default 'text',  -- 图文混合留位
  asset_key     varchar(300) null,    -- figure/table/formula 的图在 MinIO
  caption       varchar(500) null,    -- 图注 / 表注
  bbox_json     json null,            -- 页内坐标，用于高亮定位
  breadcrumb    varchar(500),         -- 书名 › 章 › 节
  heading       varchar(300) null,
  text          mediumtext,
  text_hash     char(64),             -- 增量重算依据
  token_count   int,
  page_from     int null,
  page_to       int null,
  confidence    decimal(3,2) null,
  created_at    datetime,
  key idx_source(source_id, seq)
)

-- L1 笔记
note(
  id            char(26) pk,
  owner_id      char(26) default 'single',
  title         varchar(500),
  body_md       mediumtext,
  origin        enum('self','ai')     default 'self',
  confirmed     tinyint(1)            default 1,   -- 只有 1 才算"学过"
  source_url    varchar(1000) null,   -- 预留：网页剪藏
  clipped_at    datetime null,
  created_at    datetime,
  updated_at    datetime
)

-- 笔记/块的出处关联
note_block(note_id char(26), block_id char(26), primary key(note_id, block_id))

-- 主题
topic(id char(26) pk, name varchar(200), parent_id char(26) null)

-- 断言（持久）
concept(
  id            char(26) pk,
  owner_id      char(26) default 'single',
  note_id       char(26),             -- 主要来源：L1
  block_id      char(26) null,        -- 出处
  topic_id      char(26),
  claim         varchar(1000),        -- 一句可判真假的陈述
  status        enum('active','merged','retired') default 'active',
  created_at    datetime
)

-- 题目（瞬时；frozen=1 才是收藏题）
question(
  id            char(26) pk,
  concept_id    char(26),
  type          enum('recall','explain','apply'),
  stem          text,
  answer        text,
  rubric_json   json,                 -- [{key,point,max_score}]
  explanation   text,                 -- 固定解析
  evidence_ids  json,                 -- block_id 列表
  frozen        tinyint(1) default 0,
  created_at    datetime
)

-- 作答
attempt(
  id            char(26) pk,
  question_id   char(26),
  concept_id    char(26),
  answer_text   text,
  score         decimal(4,2),
  max_score     decimal(4,2),
  rubric_result json,                 -- [{key,score,reason}]
  verdict       enum('pending','weak','ok','invalid'),
  duration_ms   int,
  created_at    datetime,
  key idx_concept(concept_id, created_at)
)
```

### 5.2 Milvus

```
collection: kb_blocks
  id          VARCHAR(26)  primary
  vector      FLOAT_VECTOR(1024)          -- bge-m3
  source_id   VARCHAR(64)  partition key  -- 按书/文档隔离
  owner_id    VARCHAR(26)                 -- 鉴权留位，检索时强制 filter
  doc_type    VARCHAR(16)                 -- pdf / md
  note_id     VARCHAR(26)                 -- L1 块才有

index: HNSW, M=16, efConstruction=200, metric=COSINE
search: ef=64~128；一致性 Bounded
```

`source_id` 做 partition key，是为了"只在这本书里找"这类过滤能走分区裁剪，而不是全量扫描后过滤。

### 5.3 MinIO

```
bucket kb-raw/
  {sha256[0:2]}/{sha256}.{ext}          原始文件，不可变
  {sha256[0:2]}/{sha256}.blocks.md      解析中间产物（可重建）
  {sha256[0:2]}/figures/{block_id}.png  图文混合 PDF 抽出的图（可重建）
  export/notes/{note_id}.md             笔记导出（可重建）

bucket kb-milvus/                       Milvus 自用，忽略
```

---

## 6. 接口

### 6.1 内部 port（Python Protocol）

```python
class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def presign(self, key: str, ttl_s: int) -> str: ...

class MetaStore(Protocol):
    def create_source(self, s: Source) -> str: ...
    def put_blocks(self, blocks: list[Block]) -> None: ...
    def fulltext_search(self, q: str, flt: Filter, k: int) -> list[Hit]: ...

class VectorStore(Protocol):
    def upsert(self, rows: list[VectorRow]) -> None: ...
    def search(self, v: list[float], flt: str | None, k: int) -> list[Hit]: ...
    def delete(self, flt: str) -> None: ...

class LLMProvider(Protocol):
    def complete(self, messages, *, json_schema=None, temperature=0.2) -> str: ...

class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

### 6.2 HTTP

```
POST   /sources                 上传文件（预签名直传 MinIO，或服务端中转）
POST   /sources/{id}/parse      触发解析
GET    /sources/{id}/preview    章节树 + 块预览 + 置信度（入库验收）
GET    /search?mode=locate      定位
POST   /ask                     问答
POST   /survey                  摸底
POST   /concepts/extract        对指定 note 懒抽取断言
POST   /quizzes                 生成一份考核
POST   /attempts                提交作答，同步返回判分
GET    /diagnosis?scope=...     薄弱项报告
GET    /review/weak             错题本
POST   /attempts/{id}/invalidate  否决题目
```

### 6.3 CLI

```
kb ingest <path>          # 支持目录批量
kb ask "问题"
kb quiz --scope recent
kb weak                   # 错题本
kb export --all           # 导出 md + sql，验证可迁移
kb reindex                # 从原始文件重建（验收用）
```

---

## 7. 范围与里程碑

### 7.1 M0：底盘 + 问答（不提考试）

| 做 | 不做 |
| --- | --- |
| 文字版 PDF、Markdown 导入 | 网页剪藏、扫描件 OCR |
| 解析 → 章节树 → 块（breadcrumb） | 图片、公式索引 |
| MinIO 原文 / MySQL 元数据 / Milvus 向量 | 多端同步、移动端 |
| 三路混合检索 | 权限、多用户 |
| 问答：逐句出处、点回原文、库外拒答 | 出题、判分、诊断 |
| CLI + 极简网页（导入 / 提问 / 看引用） | 写作模式、博客导出 |

**留位（M0 就要有，一天工作量）：** `note.origin` / `note.confirmed` 字段、`block_id` 作引用锚点、`breadcrumb`、`concept` / `question` / `attempt` 空表、`source.sha256`。

**验收标准（三条全过才算完）：**

1. 3 本书 + 50 篇笔记，导入全流程无人工干预。
2. 20 条评测问题：库内有答案的 10 条，≥ 8 条答对且引用能点回原文；库内没答案的 10 条，**10 条全部明确拒答**。
3. 删掉 Milvus 与 MySQL 全部数据，仅凭 MinIO 原始文件 + 元数据导出，一条命令重建可用库。

### 7.2 M1：学习闭环

| 阶段 | 内容 |
| --- | --- |
| M1-a | 断言懒抽取、主题归组、出题（记忆/理解）、逐条 rubric 判分、原因 + 解析 |
| M1-b | 薄弱项诊断、错题本、收藏题冻结、否决题目、应用型题目 |

**验收标准：**

1. 一篇 1500 字笔记，抽出 3–8 条断言，你可逐条改/合并/退役。
2. 出 5 道题，判分逐条给出，你自己评判"判得对不对"≥ 80%。
3. 同一答案连判 3 次，总分波动 ≤ 5 分（百分制）。
4. 连续两轮考核后，诊断报告能指出具体主题与断言，且"建议回读第 X 节"能定位到真实块。

### 7.3 版本映射

| 版本 | 内容 |
| --- | --- |
| `v0.1.0` | M0 完成：导入 + 检索 + 问答带引用 |
| `v0.2.0` | M1-a：断言 + 出题 + 判分 |
| `v0.3.0` | M1-b：诊断 + 错题本 + 收藏 |
| `v0.4.0` | 摸底（survey）+ 写作模式雏形 |
| `v0.5.0` | 图文混合 PDF：图 / 图注 / 表格（按图处理）/ 公式（原图） |
| `v0.6.0` | 其他格式：docx / epub / html / pptx / 单图 |
| `v0.7.0` | 鉴权：登录 + 角色 + 数据隔离 |

### 7.4 明确不做（v1 全周期）

多人实时协作、移动 App、插件系统、主动推送与复习调度、自动抓取全网、视频/音频转写。

### 7.5 M2：多格式（v0.5.0 / v0.6.0）

MVP 跑通之后立刻做。理由是：**带图的书才是常态**，纯文本 PDF 只是理想情况。

#### v0.5.0 图文混合 PDF

难点不在"把图抠出来"，而在**阅读顺序**：图必须插回它在文中真正的位置。顺序错了，问答时上下文错位，图注和正文对不上，引用出来的证据是假的。

```
PDF 页 → 文本块（带 bbox）
       → 图片抽取（按区域裁切，落 MinIO）
       → 图注配对（"图 3-1" 就近匹配；无编号则取下方最近段落）
       → 阅读顺序重建（按 bbox 的 y/x 排，不是按 PDF 对象流顺序）
       → 块序列 text | figure，figure 带 asset_key + caption
```

几条明确的取舍：

- **表格不做结构化还原**，按"图"处理（裁图 + 描述）。表格还原是另一个项目的量级，性价比极低。
- **公式同理**：保留原图，可选做 LaTeX 识别，不做语义理解。
- **视觉描述只按需跑**：仅对"没有图注、但被正文引用"的图调视觉模型生成一句话。全量跑又贵又没必要，大部分图注已经够检索用了。

检索时 figure 块用 `caption + 邻近段落` 拼成描述文本参与 embedding；原图保留，回答里可以直接展示。

#### v0.6.0 其他格式

统一中间层的价值在这里兑现：每种格式一个 parser adapter，输出同一个 block 模型，下游一行都不用改。

| 格式 | 解析 | 难点 |
| --- | --- | --- |
| docx | `python-docx` | 样式易丢、图文锚点 |
| epub | `ebooklib` + `bs4` | 章节结构天然，最容易 |
| html / mhtml | `trafilatura` | 正文提取与去噪 |
| pptx | `python-pptx` | 一页一块，顺序天然 |
| 单张图片 | 视觉模型 | 无文本层，只能靠描述 |

**验收：** 同一本书的 PDF 版和 EPUB 版都导入后，同一批查询的检索结果应足够接近。差异大，说明解析层有系统性偏差。

### 7.6 M3：鉴权（学习向，v0.7.0）

单独一个版本，既是给自己用（迟早要暴露到公网），也是刻意的学习目标。**放在 M0/M1 之后**——在还没跑通的时候先做登录页，是本末倒置。

**分三层做，别一次做完：**

| 层 | 内容 | 学习点 |
| --- | --- | --- |
| 认证 | 密码 argon2 哈希、会话/JWT、刷新与撤销、登录限流 | token 生命周期、撤销机制、防爆破 |
| 授权 | 角色（owner / viewer）、资源可见性（私有 / 只读 / 分享链接） | RBAC 模型、权限判定顺序 |
| 隔离 | `owner_id` 贯穿所有查询，强制注入 | 越权测试、查询层过滤 |

**一条设计约束，也是最有讲头的地方：**

隔离必须做在 **MetaStore / VectorStore 的查询层**，不是控制器层。控制器上逐个接口加过滤，漏一个接口就是全库泄露；查询层强制注入 `owner_id`，漏不掉。

这就是本方案在 5.1 / 5.2 里已经埋好 `owner_id` 的原因——现在加一列是一分钟的事，等有了几万条数据再回填就是一次迁移事故。

**验收：**

1. 10 条越权用例全过：改 id 去访问不属于自己的 source / note / concept / attempt，全部拒绝。
2. token 过期、主动撤销、登出后旧 token 立即失效。
3. 登录失败 5 次触发限流，并写审计日志。

**不做：** 第三方 OAuth、SSO、多租户计费。这些等真有多用户需求再说。

**代价：** 会引入"用户"概念和一整套登录态，所有 API 都要过中间件。所以它必须是最后一块，不能挡在前面。

---

## 8. 质量与评估

### 8.1 评测集（M0 第一周就建）

`eval/questions.yaml`，20 条起，格式：

```yaml
- id: q01
  type: in_kb            # in_kb | out_of_kb
  question: 混合检索的权重是怎么定的？
  expect:
    must_cite: [block_id 或笔记标题]
    must_contain: ["0.45", "词法"]
  notes: 答案应指向《混合检索的排序权重实验》第 2 节
```

**没有这个文件，后面所有调优都是感觉。** 每次改切分、改权重、换模型，跑一遍看分数。

### 8.2 指标

| 指标 | 目标 |
| --- | --- |
| 库内问答正确率 | ≥ 80%（20 条集） |
| 库外拒答率 | 100% |
| 引用可点回原文 | 100% |
| 检索 P95 | < 300ms（1 万块） |
| 解析后块可用率 | 人工抽查 20 块，≥ 18 块语义完整 |
| 判分一致性 | 同一答案 3 次，波动 ≤ 5 分 |
| 重建耗时 | 1 万块 < 10 分钟 |

### 8.3 重建演练

每月跑一次 `kb export --all && kb reindex`。这是长期可用性的唯一保证，也是唯一能证明"数据不是系统的囚徒"的方式。

---

## 9. 工程与版本规范

### 9.1 仓库结构

```
my-project/
├── CHANGELOG.md
├── README.md
├── docs/
│   ├── plan.md                 ← 本文
│   ├── releases/v0.1.0.md      ← 每版一份详情
│   ├── adr/0001-why-milvus.md  ← 每个技术选择的理由
│   └── mistakes.md             ← 踩过的坑
├── src/
│   ├── api/
│   ├── ingest/
│   ├── retrieval/
│   ├── answer/
│   ├── quiz/
│   ├── ports/
│   └── adapters/
├── migrations/
├── eval/
├── deploy/docker-compose.yml
└── tests/
```

### 9.2 版本规则

1. **每个能跑的版本打 annotated tag**，tag 说明一句话写清"这一版能干什么"。
2. **`CHANGELOG.md` 做索引**（Keep a Changelog 结构：Added / Changed / Fixed / Removed），每条一句话。
3. **`docs/releases/vX.Y.Z.md` 做详情**，固定六段：目标 / 做了什么 / 怎么验收 / 数据迁移 / 已知问题 / 下一步。
4. **每个版本记 `schema_version`**，迁移脚本进 `migrations/`，含升级与回退。

### 9.3 一条容易被忘的

**git 能回滚代码，回滚不了数据库。** 所以每个 tag 必须写清"这一版 schema 变没变、变了怎么退"。M0 阶段可以粗暴地约定"数据可丢弃"，但 M1 之后必须有真正的迁移脚本。

### 9.4 打 tag 的门槛

必须过当版验收清单，否则 tag 无意义——回滚回去跑不起来的版本，不叫版本。

---

## 10. 风险与对策

| 风险 | 表现 | 对策 |
| --- | --- | --- |
| PDF 解析烂尾 | 块语义断裂，问答答非所问 | 入库预览 + 置信度标黄；每本书先抽 20 块人眼验收 |
| 出题质量差 | 题目脱离笔记、解析胡说 | 强制 `evidence_ids`；你可否决；先只做记忆型 |
| 判分不一致 | 同答案两次分数差很多 | rubric 逐条判定、温度 0、单条要点必须可独立判断 |
| 练手复杂度拖垮日常 | 组件一挂就不能用 | 降级路径（见 4.4）；Milvus 永远不是唯一路径 |
| 项目变成 demo | 能跑但自己不用 | M0 验收第 2 条（20 条评测问题）+ 每周真实使用记录 |
| 范围蔓延 | 半年后变成半个 Notion | 7.4 的"不做"清单进 PR 模板，越界需求一律拒 |
| 数据被系统绑架 | 换部署就全丢 | 每月重建演练；导出 md + sql |

---

## 11. 第一周做什么

| 天 | 事项 | 产出 |
| --- | --- | --- |
| 1 | 仓库骨架、docker compose（minio / mysql / etcd / milvus）、连通性验证 | 五个容器能起，三个 port 各有 `ping` |
| 2 | MySQL DDL + `migrations/0001_init.sql`，含全部空表（留位） | 表建好，`schema_version` 记 1 |
| 3 | 上传 → MinIO → source 记录 → 解析 → block 落库（先只支持 MD） | `kb ingest 笔记.md` 能跑通 |
| 4 | PDF 解析（单栏优先）+ 预览接口 | 一本书能进库，能看到章节树 |
| 5 | 嵌入批处理 + Milvus upsert + 全文索引 | 块能召回 |
| 6 | `/ask` 打通：召回 → 生成 → 引用校验 | 能问出带出处的答案 |
| 7 | `eval/questions.yaml` 前 10 条 + 打 `v0.1.0-dev` | 有基线数字，能对比 |

第 1 版不打正式 tag，`v0.1.0` 留给 M0 全部验收通过。

---

## 12. 已定的三个默认值

| 项 | 决定 | 备注 |
| --- | --- | --- |
| 实现语言 | **Python + FastAPI ✅ 已确认** | PDF 解析、embedding、LLM SDK 生态最全；与你现有技能一致 |
| Embedding | **bge-m3 本地 CPU**（1024 维） | 数据不出门、零调用费；首次灌库跑几小时，已配断点续跑 |
| 鉴权 | **v0.7.0 才做**：登录 + 角色 + 数据隔离 | M0/M1 无鉴权，仅本机/内网访问 |

---

## 附录 A：依赖清单（Python）

| 用途 | 选型 | 备注 |
| --- | --- | --- |
| Web 框架 | `fastapi` + `uvicorn` | |
| 配置与校验 | `pydantic` + `pydantic-settings` | 配置从 `.env` 读，别散落 |
| ORM / 迁移 | `sqlalchemy` 2.x + `alembic` | 表结构由 alembic 管，别手写 DDL |
| PDF 解析 | `pymupdf`（fitz） | 能拿字符坐标，判双栏靠它 |
| 对象存储 | `minio` | 官方 SDK |
| 向量库 | `pymilvus` | |
| 嵌入 | `FlagEmbedding`（bge-m3） | 想提速可转 ONNX + int8 |
| LLM | `openai` SDK | 改 `base_url` 即可接 DeepSeek / 豆包 |
| 重试 | `tenacity` | LLM 调用必备 |
| 日志 | `structlog` | JSON 日志，排障时省命 |
| 测试 | `pytest` + `pytest-asyncio` | 越权用例、重建用例都靠它 |
| 代码质量 | `ruff` | 一个工具代替 flake8 + isort |

> `alembic` 这条别省。5.1 的 DDL 只是设计稿，真正的表结构演进靠迁移脚本，这也是 9.2 里"每版记 schema_version"的落地方式。

---

## 附录 B：分工与协作方式

原则：**没有设计空间、错了很烦、且学不到东西的，我写；需要判断、能讲进面试的，你写。**

### 我写（附理由）

| 模块 | 内容 | 为什么我来 |
| --- | --- | --- |
| 环境与骨架 | docker compose、Dockerfile、`.env.example`、settings、结构化日志 | 纯配置，没有设计空间；错一处你排查一整天 |
| 迁移脚手架 | `alembic init`、`0001_init`、迁移模板 | 机械劳动，会用 alembic 就够，不必从零造 |
| port 定义 | `src/ports/*.py` 五个 Protocol | 这是架构决策不是实现；定错了全盘返工，但改起来很便宜 |
| 测试夹具 | `tests/conftest.py`（临时 bucket / collection / 事务回滚） | 一次性投入，后面每个测试都吃红利 |
| 路由与 CLI 骨架 | FastAPI 路由注册、CLI 命令框架 | 模板代码，写十遍也不会长进 |

### 你写（核心，也是面试的弹药）

| 模块 | 你真正要搞明白的 |
| --- | --- |
| PDF 解析 | 怎么判双栏、页眉页脚怎么剔、跨页怎么合、章节怎么认 |
| 切块与 breadcrumb | 为什么 500–800 字、为什么前缀要拼路径 |
| 混合检索 | RRF 为什么不用分数归一化、相邻块怎么合并 |
| 引用校验 | 虚引用怎么识别、无据句怎么标 |
| 断言抽取 | prompt 怎么写才不抽出废话 |
| 判分 | rubric 怎么拆才判得稳 |
| 诊断聚合 | 四层判断怎么落地 |
| 降级路径 | Milvus 挂了怎么退到全文 |
| 前端 | 能导入、能问、能看引用 |

### 一起定

数据模型最终 schema（我提议你拍板）、`eval/questions.yaml` 的 20 条、每版的 release notes（你写我审）。

### 协作协议

1. **动手前先说思路**（3–5 句），我确认方向再写代码——省掉整段白写。
2. **卡住时我给线索不给代码**：三个方向 + 一个自检问题。你明确说"要答案"，我才贴实现。
3. **写完我 review**：指出问题和原因，不改你的文件。改不改你决定。
4. **每个模块先有一个会失败的测试**，再写实现。这也让 review 有共同标准。

### 单模块节奏

```
说思路 → 我确认 → 写失败测试 → 写实现 → 我 review → 记一条 mistakes.md
```

---

## 附录 C：换机与恢复

**`git clone` 只带走代码。** 完整可用的系统需要三样东西：

| 东西 | 在哪 | 怎么搬 |
| --- | --- | --- |
| 代码 | git 仓库 | `git clone` |
| 数据 | MinIO 数据卷 + MySQL | `mc mirror` / `mysqldump`；或直接拷整个 `volumes/` |
| 配置与密钥 | `.env`（绝不入库） | 密码管理器 |

标准恢复动作（同时也是每月演练）：

```bash
git clone https://github.com/datou513/my-project.git
cp .env.example .env          # 填密钥
docker compose up -d          # 空库也能起
./scripts/restore.sh          # 恢复 minio + mysql
kb reindex                    # 重建向量，验证通过
```

`.gitignore` 必须挡住：`volumes/`、`.env`、`backup/`、`models/`（bge-m3 权重几个 G）、`*.pdf`（书是数据不是代码）。

**"新机器 clone 下来、恢数据、reindex 通过"就是 7.1 第三条验收的实战版。** 练熟了，你随时可以换云服务器、搬 NAS，或者在笔记本上起一个副本。

### 对话能不能跟着走

聊天记录存在本机 `~/.dsh/sessions/` 下，按工作区路径分目录。连同该目录一起搬、且新机器工作区路径一致，通常能恢复历史对话。

但**别把这个当依赖**。真正让工作可续的是仓库里的文件：

```
docs/plan.md        ← 全部共识与设计
docs/adr/*.md       ← 每个技术选择的理由
docs/releases/*.md  ← 每版做了什么
docs/mistakes.md    ← 踩过的坑
```

换电脑、换会话、隔半年回来，只要这几份文件在，任何一次新对话读一遍就能接上。**上下文该存在仓库里，不存在聊天窗口里。**
