# Urban Signal Miner

**Urban Signal Miner** — 11-source news aggregation × AI enrichment × multi-dimensional analysis × opportunity discovery

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Vue](https://img.shields.io/badge/vue-3.5%2B-brightgreen)](https://vuejs.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> An enterprise-grade news intelligence pipeline: ingests 11 Chinese news platforms daily, enriches each article with AI-generated metadata (domain classification, entity extraction, importance scoring, causal impact assessment), stores into a dual-backend database (SQLite/MySQL with full-text search), and provides a Web Dashboard with visual analytics, multi-dimensional news search, and multi-tier analytical reports (weekly/monthly/quarterly deep dives with causal chains + opportunity maps + city comparison).

---

## Quick Start

### Web Application (Recommended)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the backend API (default: http://localhost:8000)
export ANTHROPIC_API_KEY="sk-ant-..."
uvicorn api.main:app --reload --port 8000

# 3. Start the frontend dev server (default: http://localhost:5173)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### CLI Mode

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

python run_pipeline.py                          # Full pipeline: sync → classify → index → report
python scripts/search.py -k "AI chips" -c Shenzhen -i 4  # Multi-dimension search
python scripts/gen_quarterly.py --offset -1      # Previous quarter deep analysis
```

**Input**: 600–900 raw Markdown articles/day from 11 platforms  
**Output**: Classified news index + Dashboard visualization + weekly/monthly/quarterly reports  
**Cost**: ~$15–25/month (local LLM: nearly zero)

---

## Web Features

| Page | Route | Description |
|------|-------|-------------|
| **Dashboard** | `/dashboard` | 4 stat cards + news volume line chart + domain pie chart + city/source bar charts + recent reports |
| **News Search** | `/news` | Left filter panel (keyword/domain/city/source/importance/date) + results list + detail drawer |
| **Report Center** | `/reports` | Tab bar by report type + card gallery + generate dialog (type/period/force regenerate) + progress polling |
| **Report Detail** | `/reports/:type/:key` | Sticky section nav + structured rendering (key findings/causal chain/opportunity table/ranked list) + raw markdown toggle + regenerate/delete |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/dashboard/stats?days=30` | Dashboard aggregate data |
| GET | `/api/v1/news/search?keyword=&domain=&city=&...` | Multi-dimension news search |
| GET | `/api/v1/news/{id}` | News detail |
| GET | `/api/v1/reports?report_type=&page=&page_size=` | Report list |
| GET | `/api/v1/reports/{type}/{period_key}` | Report detail (structured JSON) |
| POST | `/api/v1/reports/generate` | Trigger generation (async, returns task_id) |
| DELETE | `/api/v1/reports/{type}/{period_key}` | Delete report |
| GET | `/api/v1/tasks/{task_id}` | Poll task status |
| GET | `/api/v1/meta/{domains,cities,sources,report-types,available-periods}` | Metadata |

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
               ┌────────────────┼────────────────┐
               ▼                                 ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│      FastAPI Backend      │    │        Vue 3 Frontend            │
│  ┌────────────────────┐  │    │  ┌────────────────────────────┐  │
│  │ DashboardService   │  │    │  │ DashboardView (ECharts)    │  │
│  │ ReportService      │  │    │  │ NewsSearchView (Filter+)   │  │
│  │ MarkdownParser     │  │    │  │ ReportCenterView (Gallery) │  │
│  │ ThreadPoolExecutor │  │    │  │ ReportDetailView (Struct)  │  │
│  └────────────────────┘  │    │  │ MainLayout (Dark Theme)    │  │
└──────────────────────────┘    │  └────────────────────────────┘  │
                                └──────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **YAML frontmatter injection** (not separate metadata files) | Non-destructive: original Markdown preserved; metadata travels with content; single source of truth |
| **Dual database backend** (SQLite ↔ MySQL) | Zero-config SQLite for personal use; MySQL for multi-process/concurrent access; identical API via `db.py` |
| **Async report generation with polling** | POST returns task_id immediately; ThreadPoolExecutor generates in background; frontend polls every 2s; auto-navigates on completion |
| **Markdown → Structured JSON** | Backend parses report Markdown into section arrays; frontend renders by type (causal chain diagrams, opportunity tables, ranked lists) |
| **Multi-model routing** | `model_key="fast"` for classify/weekly/monthly; `model_key="deep"` for quarterly/causal-chain — configured in `settings.yaml` with role tags |
| **Crash recovery via `processed_files`** | Files marked processed immediately after API call; restart skips already-processed files — no duplicate API cost |

---

## Data Pipeline

### 1. Sources (11 Platforms)

| Tier | Source Key | Platform | Coverage Strategy | Weight |
|------|-----------|----------|-------------------|--------|
| **P1** | `cls-hot` | 财联社电报 | Full corpus — financial wires, highest signal density | 5 |
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
| `source` | VARCHAR(32) | ✓ | Source key |
| `source_name` | VARCHAR(64) | | Display name |
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

---

## CLI Command Reference

### Pipeline Orchestrator

```bash
python run_pipeline.py                          # Full pipeline
python run_pipeline.py --classify-limit 50      # Test mode (50 articles)
python run_pipeline.py --config-only            # Config validation only
python run_pipeline.py --skip-report            # Skip report generation
python run_pipeline.py --skip-sync              # Skip git pull
```

### Search

```bash
python scripts/search.py -k "autonomous driving"                        # Keyword
python scripts/search.py -k "semiconductor" -c Shanghai -i 4             # City + importance
python scripts/search.py -d "经济/金融" --from 2026-04-01                # Domain + date range
python scripts/search.py -k "AI" -s cls-hot -n 50                        # Source + limit
```

### Report Generation

```bash
# Periodic reports
python scripts/gen_weekly.py                     # Current week
python scripts/gen_weekly.py --week 2026-W15     # Historical week
python scripts/gen_monthly.py                    # Current month
python scripts/gen_quarterly.py                  # Current quarter
python scripts/gen_quarterly.py --offset -1      # Previous quarter

# Special reports
python scripts/gen_city_compare.py               # 6-city comparison
python scripts/gen_city_compare.py --months 6    # Extended time window
python scripts/gen_causal_chain.py --topic "AI chips"                  # Causal chain tracking
python scripts/gen_causal_chain.py --topic "housing" --months 12       # Year-long trace
```

---

## Configuration

### `config/settings.yaml` — Global settings

```yaml
database:
  type: "sqlite"                   # sqlite | mysql
  sqlite:
    path: "db/news.db"
  mysql:
    host: "localhost"
    port: 3306
    user: "root"
    password: ""                   # Empty = read from MYSQL_PASSWORD env
    database: "daily_news"
    charset: "utf8mb4"

model:
  - name: "Local-Fast"
    role: "fast"                    # Used by: classify, weekly, monthly, quarterly-phase1
    base_url_anthropic: "http://localhost:11434"
    api_key: ""                     # Empty = read from ANTHROPIC_API_KEY env
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 15000
    max_retries: 1

  - name: "Local-Deep"
    role: "deep"                    # Used by: quarterly-phase2, causal-chain
    base_url_anthropic: "http://localhost:11434"
    api_key: ""
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 30000
    max_retries: 1
```

---

## Project Structure

```
daily/
├── api/                        # FastAPI backend
│   ├── main.py                 # App entry, CORS, lifespan
│   ├── config.py               # Settings loader
│   ├── dependencies.py         # DB dependency injection
│   ├── models/                 # Pydantic models
│   ├── routers/                # dashboard, news, reports, meta
│   └── services/               # report_service, markdown_parser, dashboard_service
├── frontend/                   # Vue 3 frontend
│   ├── src/
│   │   ├── views/              # Dashboard, NewsSearch, ReportCenter, ReportDetail
│   │   ├── stores/             # Pinia stores (dashboard, news, reports)
│   │   ├── api/                # Axios API client
│   │   ├── router/             # Vue Router config
│   │   ├── layouts/            # MainLayout (dark theme + collapsible sidebar)
│   │   └── types/              # TypeScript type definitions
│   └── vite.config.ts          # Vite build config + API proxy
├── scripts/                    # Python CLI tools (existing)
│   ├── classify.py             # AI enhancement (core pipeline)
│   ├── search.py               # CLI search
│   ├── gen_weekly.py           # Weekly report
│   ├── gen_monthly.py          # Monthly report
│   ├── gen_quarterly.py        # Quarterly deep report (2-phase)
│   ├── gen_city_compare.py     # City comparison
│   ├── gen_causal_chain.py     # Causal chain tracker
│   └── utils/                  # db.py, llm_client.py, config_loader.py, etc.
├── config/                     # YAML configuration files
├── reports/                    # Generated report Markdown files
├── db/                         # SQLite database
├── logs/                       # Runtime logs
└── run_pipeline.py             # One-click pipeline orchestrator
```

---

## Deployment

### Local Development

```bash
# Terminal 1: Backend
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
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

### Production

```bash
# Backend (with gunicorn)
pip install gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Frontend (static build)
cd frontend && npm run build
# Deploy dist/ to Nginx, configure /api reverse proxy to localhost:8000
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `fastapi` + `uvicorn` | Web API framework |
| `anthropic` | Claude/Anthropic-compatible API client |
| `pyyaml` | Configuration file parsing |
| `pydantic` | AI classification + API model validation |
| `pymysql` | MySQL backend (when `database.type: mysql`) |
| `tqdm` | Batch classification progress bars |
| `vue` + `vite` | Frontend framework & build tooling |
| `element-plus` | UI component library |
| `echarts` | Data visualization charts |
| `pinia` | Frontend state management |
| `axios` | HTTP client |

Python 3.10+ required.

---

## FAQ

**Q: Can I use a local LLM instead of Claude API?**  
Yes. Point `base_url_anthropic` to your local endpoint (Ollama, vLLM, llama.cpp server). The system uses the Anthropic-compatible `/v1/messages` protocol.

**Q: How do I switch between SQLite and MySQL?**  
Change `database.type` in `config/settings.yaml`. All application code uses the same `db.py` interface — no code changes needed.

**Q: What happens if the API fails during classification?**  
Failed articles are NOT marked as processed, so they will be retried on the next pipeline run.

**Q: How long does report generation take in the web UI?**  
Depends on model speed and article count. Weekly reports typically take 30–90 seconds; quarterly deep analysis may take 3–5 minutes. The frontend shows a real-time progress bar with auto-navigation on completion.
