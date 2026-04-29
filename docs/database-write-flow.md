# 数据库表写入文档

三张表的数据插入时机、触发条件和数据来源。

---

## 表1: `news_index` — 新闻索引

**用途**：存储 AI 增强后的每条新闻的结构化元数据。

**字段**：`id`, `date`, `source`, `source_name`, `source_url`, `rank`, `title`, `domain`, `cities`, `entities`, `tags`, `importance`, `ai_summary`, `ai_why_matters`, `file_path`, `word_count`, `processed_at`

### 写入点

| 编号 | 脚本 | 函数 | 触发条件 |
|------|------|------|---------|
| ① | `classify.py` | `enhance_file()` | 新闻通过 AI 分类（`quality_pass=true` 且 `is_duplicate=false`），在文件写入 YAML frontmatter 之后立即调用 `insert_news()` |
| ② | `index_sync.py` | `sync_all()` | 从 `news-corpus/` 扫描所有已增强文件（以 `---` 开头的 .md），解析 YAML frontmatter 后调用 `insert_news()`。**全量同步/重建**，用 `REPLACE INTO` 确保幂等 |

### 数据流

```
news-corpus/20260428/cls-hot/某新闻.md  (原始 Markdown)
    │
    │ classify.py ── Claude 结构化输出 ── 判断 quality_pass + is_duplicate
    │
    ├── 跳过 (质量不过/重复) → 不插入 news_index
    │
    └── 通过 → 文件头部插入 YAML frontmatter
                │
                └── insert_news(record) → news_index 表
                     ↓
              同时写入 news_fts (SQLite) / FULLTEXT INDEX (MySQL)
```

### 重复处理

- `insert_news()` 使用 `REPLACE INTO`，以 `id` 为 PRIMARY KEY
- 重复执行 `classify.py` 或 `index_sync.py` 不会产生重复行
- `id` 格式：`{YYYYMMDD}-{source}-{rank}`，如 `20260428-cls-hot-003`

---

## 表2: `processed_files` — 文件处理状态

**用途**：跟踪哪些 `news-corpus/` 下的 .md 文件已经被处理过，避免重复调用 API 打标。

**字段**：`file_path` (PK), `processed_at`

### 写入点

| 编号 | 脚本 | 函数 | 触发条件 |
|------|------|------|---------|
| ① | `classify.py` | `process_files()` | **每处理完一条新闻**（无论是否通过质量筛选），调用 `mark_file_processed()` 标记 |
| ② | `index_sync.py` | `sync_all()` | **每同步完一条新闻**，调用 `mark_file_processed()` |

### 数据流

```
classify.py 处理逻辑：
    │
    ├── 质量通过 → enhance_file() → mark_file_processed() ✓
    │
    ├── 重复/低质量 → 跳过 ──→ mark_file_processed() ✓  (跳过也是处理过了)
    │
    └── 解析失败/异常 → 不标记，下次重试
```

### 关键语义

- **写入 `processed_files` ≠ 写入了 `news_index`**
  - 一条新闻可能"已处理"但不在 `news_index` 中（被判定为重复或低质量）
  - 这样做的好处：不会反复调 API 去分析同一条低质量新闻
- `file_path` 是相对于 `news-corpus/` 的路径，如 `20260428/cls-hot/A股新股王，一季度业绩抵去年全年.md`

### 查重流程

```
待处理文件列表 → classify.py → process_files()
    │
    ├── is_file_processed(file_path) → true  → 跳过
    │
    └── is_file_processed(file_path) → false → 调用 Claude → mark_file_processed()
```

---

## 表3: `reports_index` — 报告索引

**用途**：记录所有已生成的 AI 分析报告元数据，方便查询报告历史。

**字段**：`id` (AI), `report_type`, `period_key`, `file_path`, `news_count`, `key_findings`, `created_at`

### 写入点

| 编号 | 脚本 | report_type | period_key 示例 | 触发条件 |
|------|------|-------------|----------------|---------|
| ① | `gen_weekly.py` | `weekly` | `2026-W17` | 周报 Markdown 写入磁盘后 |
| ② | `gen_monthly.py` | `monthly` | `2026-04` | 月报 Markdown 写入磁盘后 |
| ③ | `gen_quarterly.py` | `quarterly` | `2026-Q2` | 季度深度报告写入磁盘后 |
| ④ | `gen_city_compare.py` | `special_city_compare` | `2026-04-01_2026-07-01` | 城市对比报告写入磁盘后 |
| ⑤ | `gen_causal_chain.py` | `special_causal_chain` | `causal_自动驾驶` | 因果链报告写入磁盘后 |

### 数据流

```
gen_weekly.py
    │
    ├── 收集本周 importance>=3 的新闻
    ├── 调用 Sonnet 生成报告
    ├── 写入 reports/weekly/2026-W17-report.md
    └── insert_report("weekly", "2026-W17", "reports/weekly/...", news_count=45)
           │
           └── reports_index 表

gen_city_compare.py
    │
    ├── 收集 6 城市近3个月新闻各50条
    ├── 调用 Sonnet 生成对比报告
    ├── 写入 reports/special/city-comparison-20260429.md
    └── insert_report("special_city_compare", "2026-01-29_2026-04-29", "...", news_count=180)
```

### `report_type` 枚举

| 值 | 含义 | 生成脚本 |
|----|------|---------|
| `weekly` | 周报 | `gen_weekly.py` |
| `monthly` | 月报 | `gen_monthly.py` |
| `quarterly` | 季度深度报告 | `gen_quarterly.py` |
| `special_city_compare` | 城市对比专题 | `gen_city_compare.py` |
| `special_causal_chain` | 因果链专题 | `gen_causal_chain.py` |

---

## 总结：三表关系

```
                    classify.py
                    index_sync.py
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              │
    news_index    processed_files       │
   (AI 增强后的   (已处理文件            │
    新闻结构化     去重标记)              │
    数据)                               │
          │                             │
          │   gen_weekly.py             │
          │   gen_monthly.py            │
          │   gen_quarterly.py          │
          │   gen_city_compare.py       │
          │   gen_causal_chain.py       │
          │        │                    │
          ▼        ▼                    │
      reports/   reports_index          │
     (Markdown   (报告元数据             │
      文件)      索引)                   │
```

- **`news_index`** — 原子数据层，每条新闻一行，是分析的数据源
- **`processed_files`** — 控制层，决定哪些文件需要/不需要调 API
- **`reports_index`** — 产出层，记录每次分析的结果

**幂等性**：`news_index` 和 `processed_files` 都支持重复写入（`REPLACE INTO`），`reports_index` 每次生成新报告追加一行（`INSERT`），不会覆盖旧报告。
