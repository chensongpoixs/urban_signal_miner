# Urban Signal Miner

**城市信号挖掘系统** — 11源新闻聚合 × AI增强 × 多维分析 × 机会发现

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> A production-grade news intelligence pipeline that ingests 11 Chinese news platforms daily, enriches each article with AI-generated metadata (domain classification, entity extraction, importance scoring, causal impact assessment), stores into a dual-backend database (SQLite/MySQL with full-text search), and produces multi-tier analytical reports — from weekly trend briefings to quarterly deep-dive causal chain atlases.

---

## TL;DR

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

python run_pipeline.py                          # Full pipeline: sync → classify → index → report
python scripts/search.py -k "AI芯片" -c 深圳 -i 4  # Search with multi-dimension filters
python scripts/gen_quarterly.py --offset -1      # Deep quarterly report (Opus-level analysis)
```

**Input**: 600–900 raw Markdown articles/day from 11 platforms  
**Output**: Classified news index + weekly/monthly/quarterly reports with causal chains, trend signals, city competitiveness, and opportunity maps  
**Cost**: ~$15–25/month (local LLM: nearly zero)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                               │
│  ModelScope Repo ──git pull──▶ news-corpus/{YYYYMMDD}/{source}/*.md │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     AI ENHANCEMENT (classify.py)                    │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │ Dedup   │──▶│ Domain   │──▶│ Entity   │──▶│ YAML Frontmatter │ │
│  │ (title  │   │ Classify │   │ Extract  │   │ Injection        │ │
│  │  sim)   │   │ (4 cat)  │   │ (6 types)│   │ (non-destructive)│ │
│  └─────────┘   └──────────┘   └──────────┘   └──────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      STORAGE (db.py)                                │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │   news_index    │  │  processed_files │  │  reports_index    │  │
│  │  (FTS5/FULLTEXT)│  │  (dedup tracker) │  │  (report catalog) │  │
│  └─────────────────┘  └──────────────────┘  └───────────────────┘  │
│              SQLite ←──── config switch ────▶ MySQL                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYSIS & REPORTING                             │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────────────┐  │
│  │  Weekly  │───▶│  Monthly │───▶│         Quarterly             │  │
│  │  (fast)  │    │  (fast)  │    │  Phase1: domain summary (fast)│  │
│  │  TOP10   │    │  trend   │    │  Phase2: deep causal (deep)   │  │
│  │  signals │    │  confirm  │    │  6-module atlas report       │  │
│  └──────────┘    └──────────┘    └──────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐  │
│  │  City Comparison   │  │        Causal Chain Tracker           │  │
│  │  6-city radar      │  │  upstream causes → downstream impacts │  │
│  │  talent/capital flow│  │  confidence-annotated link graph     │  │
│  └────────────────────┘  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **YAML frontmatter injection** (not separate metadata files) | Non-destructive: original Markdown preserved; metadata travels with content; single source of truth |
| **Dual database backend** (SQLite ↔ MySQL) | Zero-config SQLite for personal use; MySQL for multi-process/concurrent access; identical API via `db.py` |
| **Two-phase quarterly analysis** | Fast model compresses 300+ articles into domain summaries; deep model reasons over compressed context — avoids token limits without losing signal |
| **Multi-model routing** | `model_key="fast"` for classify/weekly/monthly; `model_key="deep"` for quarterly/causal-chain — both configured in `settings.yaml` with role tags |
| **Crash recovery via `processed_files`** | Every file is marked processed immediately after API call (pass or skip). On restart, already-processed files are skipped — no duplicate API cost |

---

## Data Pipeline

### 1. Sources (11 Platforms)

| Tier | Source Key | Platform | Coverage Strategy | Weight |
|------|-----------|----------|-------------------|--------|
| **P1** | `cls-hot` | 财联社电报 | Full corpus — financial wires with highest signal density | 5 |
| **P1** | `wallstreetcn-hot` | 华尔街见闻 | Full corpus — macro/finance deep dives | 5 |
| **P1** | `thepaper` | 澎湃新闻 | Full corpus — policy/social investigative reporting | 4 |
| **P2** | `toutiao` | 今日头条 | AI-filtered — broad coverage, high noise floor | 3 |
| **P2** | `zhihu` | 知乎 | AI-filtered — high-quality discourse on trending topics | 3 |
| **P2** | `ifeng` | 凤凰网 | AI-filtered — general news with policy angles | 3 |
| **P3** | `weibo` | 微博热搜 | Top-20 only — social sentiment barometer | 2 |
| **P3** | `baidu` | 百度热搜 | Top-20 only — mass-audience temperature check | 2 |
| **P3** | `bilibili-hot-search` | B站热搜 | Top-20 only — youth culture/trend signals | 2 |
| **P3** | `douyin` | 抖音热点 | Top-20 only — viral content detection | 1 |
| **P3** | `tieba` | 贴吧热议 | Top-20 only — community discourse sampling | 1 |

### 2. AI Enhancement (classify.py)

Each raw Markdown article is enriched with a YAML frontmatter block:

```yaml
---
id: "20260428-cls-hot-003"
date: "2026-04-28"
source: "cls-hot"
source_name: "财联社电报"
source_url: "https://www.cls.cn/detail/2357060"
rank: 8
title: "A股新股王，一季度业绩抵去年全年"
domain: ["经济/金融", "科技/AI"]
cities: ["深圳"]
entities:
  - name: "源杰科技"
    type: "company"
  - name: "CW光源"
    type: "technology"
tags: ["光通信", "数据中心", "半导体", "A股", "业绩爆发"]
importance: 4
ai_summary: "源杰科技一季度营收3.55亿同比增321%，净利润1.79亿增1153%，股价1418元超越茅台成A股新股王。"
ai_why_matters: "AI算力需求正在向产业链上游光通信/光芯片传导，源杰科技的业绩爆发是AI基础设施投资逻辑的强验证信号"
---
```

**Classification Dimensions**:

| Field | Type | Description |
|-------|------|-------------|
| `domain` | Multi-select (4 categories) | 科技/AI, 经济/金融, 政治/国际关系, 社会/民生 |
| `cities` | Multi-select (6 cities) | 北京, 上海, 深圳, 苏州, 南京, 淮安 |
| `entities` | Structured (6 types) | company, person, policy, technology, product, organization |
| `tags` | Free-form (3–8) | Domain-specific keywords |
| `importance` | 1–5 scale | 1=noise, 3=signal, 5=paradigm-shift |
| `ai_summary` | 50–150 chars | Executive summary |
| `ai_why_matters` | Free text | Causal impact assessment |

**Quality Gates**:
- **Title similarity check** (`difflib.SequenceMatcher`): Skip if ≥80% similar to existing article on same date
- **LLM `is_duplicate` / `quality_pass`**: Second-pass AI dedup + spam/clickbait filter
- **Throughput**: ~5–30 articles/batch (configurable), ~1s interval between calls (configurable rate limiting)

### 3. Indexing (index_sync.py)

Two modes:
- **Full sync** (default): Scans all enhanced `.md` files, parses YAML frontmatter, `REPLACE INTO` database (idempotent)
- **Incremental sync** (`--incremental`): Only syncs files not yet in `processed_files` table

---

## Database Schema

### `news_index` — Atomic news records

| Column | Type | Index | Description |
|--------|------|-------|-------------|
| `id` | VARCHAR(64) PK | PRIMARY | `{YYYYMMDD}-{source}-{rank}` |
| `date` | DATE | ✓ | Publication date |
| `source` | VARCHAR(32) | ✓ | Source key (e.g. `cls-hot`) |
| `source_name` | VARCHAR(64) | | Display name (e.g. `财联社电报`) |
| `title` | VARCHAR(512) | FULLTEXT | Article headline |
| `domain` | JSON | | Multi-select domain classification |
| `cities` | JSON | | Multi-select city association |
| `entities` | JSON | | Extracted named entities |
| `tags` | JSON | | Free-form keyword tags |
| `importance` | TINYINT | ✓ | 1–5 significance score |
| `ai_summary` | TEXT | FULLTEXT | AI-generated summary |
| `ai_why_matters` | TEXT | | Causal impact rationale |
| `file_path` | VARCHAR(256) | | Relative path in `news-corpus/` |

### `processed_files` — Dedup control plane

| Column | Type | Description |
|--------|------|-------------|
| `file_path` | VARCHAR(512) PK | Relative path in `news-corpus/` |
| `processed_at` | DATETIME | When the file was last processed |

### `reports_index` — Report catalog

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT AI PK | Auto-increment |
| `report_type` | VARCHAR(32) | `weekly`, `monthly`, `quarterly`, `special_city_compare`, `special_causal_chain` |
| `period_key` | VARCHAR(32) | Period identifier (e.g. `2026-W17`, `2026-Q2`) |
| `file_path` | VARCHAR(256) | Relative path to report Markdown |
| `news_count` | INT | Number of source articles |
| `key_findings` | TEXT | First 500 chars of report body |
| `created_at` | DATETIME | Generation timestamp |

---

## Report System

### Hierarchy

```
 WEEKLY (every Sunday)          MONTHLY (1st of month)         QUARTERLY (start of quarter)
 ─────────────────────          ──────────────────────         ────────────────────────────
 Model: fast                    Model: fast                    Model: Phase1=fast + Phase2=deep
                                                                
 ✓ TOP 10 events                ✓ Trend confirmation          ✓ Core narrative arcs (3–5)
 ✓ Domain dynamics (4 sectors)  ✓ Cross-domain causal links   ✓ Causal chain atlas (5+ chains)
 ✓ Trend signals                ✓ City monthly comparison     ✓ Underlying mechanisms (5+ laws)
   (accelerating/decelerating/  ✓ Key entity movements        ✓ Trend identification
    new emergence)              ✓ Monthly opportunity scan    ✓ City competitive landscape
 ✓ City tracking (6 cities)     ✓ Next-month outlook          ✓ Opportunity map
 ✓ Opportunity hints                                           (investment/career/business
 ✓ Next-week watchpoints                                       with confidence & time window)
                                                               ✓ Information blind spots

 SPECIAL REPORTS (on-demand)
 ────────────────────────────
 City Comparison: 6-city radar chart + talent/capital flow + development gap analysis
 Causal Chain: upstream cause trace + downstream impact prediction + counterfactual reasoning
```

### Quarterly Deep Report Modules

| # | Module | Methodology |
|---|--------|-------------|
| 1 | **Core Narratives** | Synthesize quarter's events into 3–5 thematic storylines |
| 2 | **Causal Chain Atlas** | Event A → B → C with derivation logic, evidence (specific headlines + dates), uncertainty annotation |
| 3 | **Underlying Mechanisms** | Extract recurring socio-economic-political patterns from news, each backed by ≥3 specific events, with boundary conditions and actionable insights |
| 4 | **Trend Forecast** | Accelerating trends, decelerating trends, potential inflection points for next quarter |
| 5 | **City Competition** | 6-city radar on policy intensity, capital activity, talent attraction, industrial base, innovation vitality — with flow inference from actual news |
| 6 | **Opportunity Map** | Investment/career/business opportunities with confidence level and time window |

---

## Command Reference

### Pipeline Orchestrator

```bash
python run_pipeline.py                          # Full pipeline
python run_pipeline.py --classify-limit 50      # Test mode (50 articles)
python run_pipeline.py --config-only            # Config validation only
python run_pipeline.py --skip-report            # Skip report generation
python run_pipeline.py --skip-sync              # Skip git pull
```

### Individual Steps

```bash
# Data sync
python scripts/sync_news.py                     # git pull from ModelScope

# AI classification
python scripts/classify.py --dry-run            # Preview mode (no changes)
python scripts/classify.py --limit 10           # Process only 10 articles (testing)
python scripts/classify.py                      # Process all pending
python scripts/classify.py --files file1.md file2.md  # Specific files only

# Index sync
python scripts/index_sync.py                    # Full rebuild
python scripts/index_sync.py --incremental      # Only new files

# Configuration check
python scripts/config_validate.py               # Pre-flight validation
```

### Search

```bash
# Full-text search with multi-dimension filters
python scripts/search.py -k "自动驾驶"                          # Keyword
python scripts/search.py -k "半导体" -c 上海 -i 4                # City + importance
python scripts/search.py -d "经济/金融" --from 2026-04-01        # Domain + date range
python scripts/search.py -k "AI" -s cls-hot -n 50                # Source + limit

# Output formats
python scripts/search.py -k "芯片" --format json                  # JSON output
python scripts/search.py -k "芯片" --format csv -o results.csv    # CSV export
python scripts/search.py -k "芯片" --count                        # Count only
```

### Report Generation

```bash
# Periodic reports
python scripts/gen_weekly.py                     # Current week
python scripts/gen_weekly.py --week 2026-W15     # Historical week
python scripts/gen_monthly.py                    # Current month
python scripts/gen_monthly.py --month 2026-03    # Historical month
python scripts/gen_quarterly.py                  # Current quarter
python scripts/gen_quarterly.py --offset -1      # Previous quarter

# Special reports
python scripts/gen_city_compare.py               # 6-city comparison (last 3 months)
python scripts/gen_city_compare.py --months 6    # Extended time window
python scripts/gen_causal_chain.py --topic "AI芯片"              # Causal chain tracking
python scripts/gen_causal_chain.py --topic "房价" --months 12     # Year-long trace
```

---

## Configuration

### `config/settings.yaml` — Global settings

```yaml
project:
  news_dir: "news-corpus"

model:
  - name: "Local-Fast"
    role: "fast"                      # Used by: classify, weekly, monthly, quarterly-phase1
    base_url_anthropic: "http://localhost:11434"
    api_key: ""                       # Empty = read from ANTHROPIC_API_KEY env
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 15000
    max_retries: 1

  - name: "Local-Deep"
    role: "deep"                      # Used by: quarterly-phase2, causal-chain
    base_url_anthropic: "http://localhost:11434"
    api_key: ""
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 30000
    max_retries: 1

llm_limits:
  classify_max_tokens: 2048
  classify_batch_size: 30            # Articles per batch
  classify_interval_seconds: 1       # Rate limiting between API calls
  classify_body_chars: 3000          # Article body truncation
  weekly_max_tokens: 4096
  monthly_max_tokens: 8192
  quarterly_max_tokens: 8192
  special_max_tokens: 4096

dedup:
  title_similarity_threshold: 0.8    # difflib threshold for pre-LLM dedup

database:
  type: "sqlite"                     # sqlite | mysql
  sqlite:
    path: "db/news.db"
  mysql:
    host: "localhost"
    port: 3306
    user: "root"
    password: ""                     # Empty = read from MYSQL_PASSWORD env
    database: "daily_news"
    charset: "utf8mb4"
```

### `config/cities.yaml`

Each of the 6 cities defines `keywords` (place names + institution names for pre-filtering) and `focus_areas` (domain-specific tracking priorities). The keyword list is used by `classify.py` for pre-LLM city matching to reduce API costs.

### `config/domains.yaml`

4 top-level domains (科技/AI, 经济/金融, 政治/国际关系, 社会/民生) with sub-domains and keyword indicators for classification.

### `config/source_weight.yaml`

11 sources with `weight` (1–5), `full_process` flag (true = full corpus, false = selective), and `top_only` flag (true = top-20 only).

---

## Deployment

### Local (Personal Use)

```bash
# Prerequisites
pip install -r requirements.txt

# Clone news corpus
git clone https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus.git news-corpus

# Run pipeline
python run_pipeline.py
```

### Cron (Automated Daily)

```cron
# Sync + classify every morning at 8:00 AM
0 8 * * * cd /path/to/daily && python run_pipeline.py --skip-report >> logs/cron.log 2>&1

# Weekly report every Sunday at 18:00
0 18 * * 0 cd /path/to/daily && python scripts/gen_weekly.py >> logs/cron.log 2>&1

# Monthly report on the 1st at 10:00
0 10 1 * * cd /path/to/daily && python scripts/gen_monthly.py >> logs/cron.log 2>&1
```

### Production Considerations

- **Database**: Use MySQL for concurrent access; the dual-backend architecture makes the switch transparent
- **LLM Endpoint**: Configure `role: "fast"` and `role: "deep"` models separately. For production, use Anthropic API for `deep` and a local/cheaper endpoint for `fast`
- **Logging**: All logs use `RotatingFileHandler` (10MB × 5 backups) under `logs/`
- **Crash Recovery**: `processed_files` table ensures classify can resume without re-processing. Failed articles are NOT marked as processed, so they retry on next run
- **Rate Limiting**: `classify_interval_seconds` in settings prevents API throttling

---

## Development

### Project Structure

```
daily/
├── config/                  # YAML configuration files
├── news-corpus/             # ModelScope repo (git submodule equivalent)
├── scripts/
│   ├── sync_news.py         # Step 1: git pull
│   ├── classify.py          # Step 2: AI enhancement (core pipeline)
│   ├── index_sync.py        # Step 3: database sync
│   ├── search.py            # CLI search tool
│   ├── gen_weekly.py        # Weekly report
│   ├── gen_monthly.py       # Monthly report
│   ├── gen_quarterly.py     # Quarterly deep report (2-phase)
│   ├── gen_city_compare.py  # City comparison special report
│   ├── gen_causal_chain.py  # Causal chain special report
│   ├── config_validate.py   # Pre-flight config check
│   └── utils/
│       ├── db.py            # DB abstraction (SQLite/MySQL)
│       ├── llm_client.py    # LLM API wrapper (Anthropic-compatible)
│       ├── config_loader.py # YAML config reader
│       ├── file_utils.py    # File scanning utilities
│       └── logging_config.py # Unified logging (RotatingFileHandler)
├── run_pipeline.py          # One-click orchestrator
├── reports/                 # Generated reports
│   ├── weekly/
│   ├── monthly/
│   ├── quarterly/
│   └── special/
├── db/                      # SQLite database (if using SQLite)
├── logs/                    # Runtime logs (10MB rotation × 5)
└── docs/                    # Documentation
```

### Key Design Patterns

**Dual-Backend Database**: `_DB` class initializes either SQLite or MySQL based on `settings.yaml`. All public functions (`insert_news()`, `search_news()`, etc.) work identically regardless of backend. Placeholder conversion (`?` → `%s`) happens automatically in `execute()`.

**Safe LLM Wrapper**: `chat_safe()` catches all exceptions and returns error text instead of crashing — critical for report generators that must produce output even when APIs fail.

**Non-Destructive Enhancement**: `classify.py` prepends YAML frontmatter to original Markdown files. The original content is preserved verbatim below the `---` delimiter. Re-running is safe (files with existing frontmatter are skipped).

**Crash Recovery**: Files are marked in `processed_files` immediately after the API call — whether the article passed quality gates or was skipped. This ensures no duplicate API costs on restart.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude/Anthropic-compatible API client |
| `pyyaml` | Configuration file parsing |
| `pydantic` | Structured output validation for AI classification |
| `pymysql` | MySQL backend (optional — only if `database.type: mysql`) |
| `tqdm` | Progress bars for batch classification |

Python 3.10+ required.

---

## FAQ

**Q: Can I use a local LLM instead of Claude API?**  
Yes. Set `base_url_anthropic` to your local endpoint (e.g., Ollama, vLLM, llama.cpp server). The system uses the Anthropic-compatible `/v1/messages` protocol. Configure two model entries with `role: "fast"` and `role: "deep"` for cost optimization.

**Q: How do I switch between SQLite and MySQL?**  
Change `database.type` in `config/settings.yaml`. All application code uses the same `db.py` interface — no code changes needed. MySQL tables are auto-created with proper `utf8mb4` charset.

**Q: What happens if the API fails during classification?**  
The failed article is NOT marked as processed, so it will be retried on the next pipeline run. All other articles in the batch continue processing. The progress bar shows which files succeeded/failed.

**Q: Can I backfill reports for past periods?**  
Yes. Weekly reports support `--week 2026-W15`, monthly reports support `--month 2026-03`. Quarterly reports use `--offset` (0=current, -1=previous, -2=two quarters ago, etc.).
