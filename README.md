# Urban Signal Miner

**城市信号挖掘系统** — 11源新闻聚合 × AI增强 × 多维分析 × 机会发现

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![Vue](https://img.shields.io/badge/vue-3.5%2B-brightgreen)](https://vuejs.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 企业级新闻情报管线：每日自动接入 11 个中文平台新闻，通过 AI 对每条新闻进行领域分类、实体提取、重要性打分、因果影响评估，存入双后端数据库（SQLite/MySQL，支持全文检索），提供 Web Dashboard 可视化总览、多维新闻搜索、以及多层次分析报告（周报/月报/季度因果链+机会发现+城市对比）。

---

## 快速开始

### Web 应用（推荐）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动后端 API（默认 http://localhost:8000）
export ANTHROPIC_API_KEY="sk-ant-..."
uvicorn api.main:app --reload --port 8000

#  uvicorn api.main:app --reload --port 8003  --host  192.168.3.2

# 3. 启动前端开发服务器（默认 http://localhost:5173）
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:5173` 即可使用。

### CLI 模式

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

python run_pipeline.py                           # 一键流水线：同步→打标→索引→报告
python scripts/search.py -k "AI芯片" -c 深圳 -i 4  # 多维度搜索
python scripts/gen_quarterly.py --offset -1       # 上一季度深度报告
```

**输入**：每日 600–900 条原始 Markdown 新闻（11 个平台）  
**产出**：结构化新闻索引 + Dashboard 可视化 + 周报/月报/季度深度报告  
**成本**：本地模型几乎为零；云端 API 约 $15–25/月

---

## Web 功能

| 页面 | 路由 | 功能 |
|------|------|------|
| **Dashboard** | `/dashboard` | 4 统计卡片 + 新闻量折线图 + 领域饼图 + 城市/来源柱状图 + 最新报告 |
| **News Search** | `/news` | 左侧多维筛选面板（关键词/领域/城市/来源/重要性/日期） + 右侧结果列表 + 详情抽屉 |
| **Report Center** | `/reports` | Tab 切换报告类型 + 报告卡片画廊 + 生成弹窗（选类型/周期/强制重新生成） + 进度轮询 |
| **Report Detail** | `/reports/:type/:key` | 左侧目录导航 + 结构化渲染（关键发现/因果链/机会表格/排名列表） + Raw Markdown 切换 + 重新生成/删除 |

### API 端点

| Method | Endpoint | 说明 |
|--------|----------|------|
| GET | `/api/v1/dashboard/stats?days=30` | 仪表盘聚合数据 |
| GET | `/api/v1/news/search?keyword=&domain=&city=&...` | 多维新闻搜索 |
| GET | `/api/v1/news/{id}` | 新闻详情 |
| GET | `/api/v1/reports?report_type=&page=&page_size=` | 报告列表 |
| GET | `/api/v1/reports/{type}/{period_key}` | 报告详情（结构化 JSON） |
| POST | `/api/v1/reports/generate` | 触发生成（异步，返回 task_id） |
| DELETE | `/api/v1/reports/{type}/{period_key}` | 删除报告 |
| GET | `/api/v1/tasks/{task_id}` | 任务状态轮询 |
| GET | `/api/v1/meta/{domains,cities,sources,report-types,available-periods}` | 元数据 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        数据接入层                                    │
│  ModelScope 仓库 ──git pull──▶ news-corpus/{YYYYMMDD}/{source}/*.md │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AI 增强 (classify.py)                           │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐ │
│  │ 标题去重 │──▶│ 领域分类 │──▶│ 实体提取 │──▶│ YAML Frontmatter │ │
│  │(相似度)  │   │ (4大类)  │   │ (6类型)  │   │ 注入（无损增强）  │ │
│  └─────────┘   └──────────┘   └──────────┘   └──────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      数据存储 (db.py)                                │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │   news_index    │  │  processed_files │  │  reports_index    │  │
│  │  (全文检索)      │  │  (去重跟踪)       │  │  (报告目录)        │  │
│  └─────────────────┘  └──────────────────┘  └───────────────────┘  │
│              SQLite ←──── 配置切换 ────▶ MySQL                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
               ┌────────────────┼────────────────┐
               ▼                                 ▼
┌──────────────────────────┐    ┌──────────────────────────────────┐
│      FastAPI 后端         │    │       Vue 3 前端                  │
│  ┌────────────────────┐  │    │  ┌────────────────────────────┐  │
│  │ DashboardService   │  │    │  │ DashboardView (ECharts)    │  │
│  │ ReportService      │  │    │  │ NewsSearchView (Filter+)   │  │
│  │ MarkdownParser     │  │    │  │ ReportCenterView (Gallery) │  │
│  │ ThreadPoolExecutor │  │    │  │ ReportDetailView (Struct)  │  │
│  └────────────────────┘  │    │  │ MainLayout (Dark Theme)    │  │
└──────────────────────────┘    │  └────────────────────────────┘  │
                                └──────────────────────────────────┘
```

### 核心设计决策

| 决策 | 理由 |
|------|------|
| **YAML frontmatter 注入**（而非独立元数据文件） | 无损增强：原始 Markdown 完整保留；元数据随内容走；单一数据源 |
| **数据库双后端**（SQLite ↔ MySQL） | 个人使用零配置 SQLite；多进程/并发场景切换 MySQL；`db.py` 统一接口，上层零改动 |
| **异步报告生成 + 轮询** | POST 立即返回 task_id，ThreadPoolExecutor 后台生成，前端每 2s 轮询，生成完成自动跳转 |
| **Markdown → 结构化 JSON** | 后端解析报告 Markdown 为 section 数组，前端按类型渲染（因果链图/机会表格/排名列表） |
| **多模型路由** | 打标/周报/月报用 `model_key="fast"`；季度深度/因果链用 `model_key="deep"`——在 `settings.yaml` 中通过 `role` 标签区分 |
| **断点续跑机制** | 每条新闻处理完立即写入 `processed_files`，重启时自动跳过已处理文件——零重复 API 成本 |

---

## 数据管线

### 一、11 个新闻来源

| 层级 | 来源标识 | 平台 | 处理策略 | 权重 |
|------|---------|------|---------|------|
| **P1** | `cls-hot` | 财联社电报 | 全量精标 — 财经快讯，信号密度最高 | 5 |
| **P1** | `wallstreetcn-hot` | 华尔街见闻 | 全量精标 — 宏观/金融深度解读 | 5 |
| **P1** | `thepaper` | 澎湃新闻 | 全量精标 — 政策/社会调查报道 | 4 |
| **P2** | `toutiao` | 今日头条 | AI 筛选 — 覆盖面广，噪音较高 | 3 |
| **P2** | `zhihu` | 知乎 | AI 筛选 — 热点深度讨论 | 3 |
| **P2** | `ifeng` | 凤凰网 | AI 筛选 — 综合新闻，政策视角 | 3 |
| **P3** | `weibo` | 微博热搜 | 仅取 Top20 — 社会情绪晴雨表 | 2 |
| **P3** | `baidu` | 百度热搜 | 仅取 Top20 — 大众关注度检测 | 2 |
| **P3** | `bilibili-hot-search` | B站热搜 | 仅取 Top20 — 年轻群体趋势信号 | 2 |
| **P3** | `douyin` | 抖音热点 | 仅取 Top20 — 病毒式传播检测 | 1 |
| **P3** | `tieba` | 贴吧热议 | 仅取 Top20 — 社区舆论采样 | 1 |

### 二、AI 增强格式

每条原始 Markdown 新闻被注入 YAML frontmatter 元数据块：

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

**分类维度**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `domain` | 多选（4大类） | 科技/AI、经济/金融、政治/国际关系、社会/民生 |
| `cities` | 多选（6城市） | 北京、上海、深圳、苏州、南京、淮安 |
| `entities` | 结构化（6类型） | company(公司)、person(人物)、policy(政策)、technology(技术)、product(产品)、organization(机构) |
| `tags` | 自由标签（3–8个） | 领域关键词 |
| `importance` | 1–5 分 | 1=噪音、3=信号、5=范式转折 |
| `ai_summary` | 50–150字 | 精炼摘要 |
| `ai_why_matters` | 自由文本 | 因果影响评估 |

**质量门控**：
- **标题相似度检测**（`difflib.SequenceMatcher`）：与同日已入库新闻标题相似度 ≥80% 则跳过
- **LLM 二次去重**（`is_duplicate`）+ 质量筛选（`quality_pass`）：过滤广告/八卦/无实质内容
- **处理吞吐**：每批 5–30 条（可配置），条间间隔 1 秒（可配置速率限制）

### 三、索引同步 (index_sync.py)

两种模式：
- **全量同步**（默认）：扫描所有已增强 `.md` 文件，解析 YAML frontmatter，`REPLACE INTO` 入库（幂等）
- **增量同步**（`--incremental`）：仅同步 `processed_files` 中不存在的文件

---

## 数据库设计

### `news_index` — 新闻原子数据

| 字段 | 类型 | 索引 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(64) PK | PRIMARY | `{YYYYMMDD}-{source}-{rank}` |
| `date` | DATE | ✓ | 发布日期 |
| `source` | VARCHAR(32) | ✓ | 来源标识 |
| `source_name` | VARCHAR(64) | | 来源显示名 |
| `title` | VARCHAR(512) | FULLTEXT | 新闻标题 |
| `domain` | JSON | | 领域分类（多选） |
| `cities` | JSON | | 城市关联（多选） |
| `entities` | JSON | | 命名实体 |
| `tags` | JSON | | 关键词标签 |
| `importance` | TINYINT | ✓ | 重要性 1–5 |
| `ai_summary` | TEXT | FULLTEXT | AI 摘要 |
| `ai_why_matters` | TEXT | | 因果影响评估 |
| `file_path` | VARCHAR(256) | | `news-corpus/` 内相对路径 |

### `processed_files` — 去重控制面

| 字段 | 类型 | 说明 |
|------|------|------|
| `file_path` | VARCHAR(512) PK | `news-corpus/` 内相对路径 |
| `processed_at` | DATETIME | 最近一次处理时间 |

### `reports_index` — 报告目录

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT AI PK | 自增主键 |
| `report_type` | VARCHAR(32) | `weekly`、`monthly`、`quarterly`、`special_city_compare`、`special_causal_chain` |
| `period_key` | VARCHAR(32) | 周期标识（如 `2026-W17`、`2026-Q2`） |
| `file_path` | VARCHAR(256) | 报告 Markdown 相对路径 |
| `news_count` | INT | 原始新闻数量 |
| `key_findings` | TEXT | 报告正文前 500 字符摘要 |
| `created_at` | DATETIME | 生成时间 |

---

## 报告体系

### 三层分析节奏

```
 周报（每周日）              月报（每月1日）               季度深度报告（每季度初）
 ────────────────           ────────────────             ───────────────────────
 模型: fast                 模型: fast                   模型: 阶段1=fast + 阶段2=deep

 ✓ 本周 TOP 10 事件         ✓ 趋势确认/证伪              ✓ 核心叙事线（3–5条）
 ✓ 四大领域动态              ✓ 跨领域因果传导             ✓ 因果链图谱（5+条链路）
 ✓ 趋势信号                  ✓ 城市月度对比               ✓ 底层运行规律（5+条规律）
   （加速/减速/新出现）       ✓ 关键实体动向               ✓ 趋势识别与预判
 ✓ 城市动态追踪（6城）       ✓ 月度机会扫描               ✓ 城市竞争态势
 ✓ 机会提示                  ✓ 下月前瞻                   ✓ 机会地图
 ✓ 下周关注点                                              （投资/职业/商业，
                                                           含置信度与时间窗口）
                                                          ✓ 信息盲区

 专题报告（按需生成）
 ────────────────
 城市对比：6城竞争力雷达 + 人才/资本流向推断 + 发展时差分析
 因果链追踪：上游原因追溯 + 下游影响预测 + 反事实推演
```

---

## CLI 命令参考

### 一键流水线

```bash
python run_pipeline.py                           # 完整流水线
python run_pipeline.py --classify-limit 50       # 测试模式（仅打标50条）
python run_pipeline.py --config-only             # 仅校验配置
python run_pipeline.py --skip-report             # 跳过报告生成
python run_pipeline.py --skip-sync               # 跳过 git pull
```

### 单步执行

```bash
# 数据同步
python scripts/sync_news.py                      # 从 ModelScope git pull

# AI 打标
python scripts/classify.py --dry-run             # 预览模式
python scripts/classify.py --limit 10            # 仅处理10条（测试）
python scripts/classify.py --files a.md b.md     # 指定文件

# 索引同步
python scripts/index_sync.py                     # 全量重建
python scripts/index_sync.py --incremental       # 仅同步新文件
```

### 搜索

```bash
python scripts/search.py -k "自动驾驶"                            # 关键词搜索
python scripts/search.py -k "半导体" -c 上海 -i 4                 # 城市 + 重要性
python scripts/search.py -d "经济/金融" --from 2026-04-01         # 领域 + 日期范围
python scripts/search.py -k "AI" -s cls-hot -n 50                 # 来源 + 条数
```

### 报告生成

```bash
# 周期性报告
python scripts/gen_weekly.py                      # 本周周报
python scripts/gen_weekly.py --week 2026-W15      # 历史周报
python scripts/gen_monthly.py                     # 本月月报
python scripts/gen_quarterly.py                   # 当前季度
python scripts/gen_quarterly.py --offset -1       # 上一季度

# 专题报告
python scripts/gen_city_compare.py                # 6城市对比
python scripts/gen_city_compare.py --months 6     # 扩展时间窗口
python scripts/gen_causal_chain.py --topic "AI芯片"               # 因果链追踪
python scripts/gen_causal_chain.py --topic "房价" --months 12     # 一年回溯
```

---

## 配置说明

### `config/settings.yaml` — 全局配置

```yaml
database:
  type: "sqlite"                   # sqlite | mysql
  sqlite:
    path: "db/news.db"
  mysql:
    host: "localhost"
    port: 3306
    user: "root"
    password: ""                   # 留空则从环境变量 MYSQL_PASSWORD 读取
    database: "daily_news"
    charset: "utf8mb4"

model:
  - name: "Local-Fast"
    role: "fast"                    # classify, weekly, monthly, quarterly-phase1
    base_url_anthropic: "http://localhost:11434"
    api_key: ""                     # 留空则从 ANTHROPIC_API_KEY 环境变量
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 15000
    max_retries: 1

  - name: "Local-Deep"
    role: "deep"                    # quarterly-phase2, causal-chain
    base_url_anthropic: "http://localhost:11434"
    api_key: ""
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 30000
    max_retries: 1
```

---

## 目录结构

```
daily/
├── api/                        # FastAPI 后端
│   ├── main.py                 # App 入口, CORS, 生命周期
│   ├── config.py               # 配置读取
│   ├── dependencies.py         # DB 依赖注入
│   ├── models/                 # Pydantic 模型
│   ├── routers/                # dashboard, news, reports, meta
│   └── services/               # report_service, markdown_parser, dashboard_service
├── frontend/                   # Vue 3 前端
│   ├── src/
│   │   ├── views/              # Dashboard, NewsSearch, ReportCenter, ReportDetail
│   │   ├── stores/             # Pinia 状态管理 (dashboard, news, reports)
│   │   ├── api/                # Axios API 客户端
│   │   ├── router/             # Vue Router 配置
│   │   ├── layouts/            # MainLayout (暗色主题 + 侧边栏)
│   │   └── types/              # TypeScript 类型定义
│   └── vite.config.ts          # Vite 构建配置 + API 代理
├── scripts/                    # Python CLI 工具 (现有)
│   ├── classify.py             # AI 增强打标（核心管线）
│   ├── search.py               # CLI 搜索
│   ├── gen_weekly.py           # 周报生成
│   ├── gen_monthly.py          # 月报生成
│   ├── gen_quarterly.py        # 季度深度报告
│   ├── gen_city_compare.py     # 城市对比
│   ├── gen_causal_chain.py     # 因果链追踪
│   └── utils/                  # db.py, llm_client.py, config_loader.py 等
├── config/                     # YAML 配置文件
├── reports/                    # 生成的报告 Markdown 文件
├── db/                         # SQLite 数据库
├── logs/                       # 运行日志
└── run_pipeline.py             # 一键流水线编排器
```

---

## 部署

### 本地开发

```bash
# 终端 1: 后端
uvicorn api.main:app --reload --port 8000

# 终端 2: 前端
cd frontend && npm run dev
```

### Cron 定时任务

```cron
# 每天早上8点：同步 + 打标
0 8 * * * cd /path/to/daily && python run_pipeline.py --skip-report >> logs/cron.log 2>&1

# 每周日晚18点：生成周报
0 18 * * 0 cd /path/to/daily && python scripts/gen_weekly.py >> logs/cron.log 2>&1

# 每月1号上午10点：生成月报
0 10 1 * * cd /path/to/daily && python scripts/gen_monthly.py >> logs/cron.log 2>&1
```

### 生产环境

```bash
# 后端（使用 gunicorn）
pip install gunicorn
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 前端（构建静态文件）
cd frontend && npm run build
# 将 dist/ 部署到 Nginx，配置 /api 反向代理到 localhost:8000
```

---

## 依赖

| 包 | 用途 |
|----|------|
| `fastapi` + `uvicorn` | Web API 框架 |
| `anthropic` | Claude/Anthropic 兼容端点 API 客户端 |
| `pyyaml` | 配置文件解析 |
| `pydantic` | AI 分类 + API 模型校验 |
| `pymysql` | MySQL 后端（`database.type: mysql` 时需要） |
| `tqdm` | 批量打标进度条 |
| `vue` + `vite` | 前端框架与构建工具 |
| `element-plus` | UI 组件库 |
| `echarts` | 数据可视化图表 |
| `pinia` | 前端状态管理 |
| `axios` | HTTP 客户端 |

---

## FAQ

**问：能用本地 LLM 替代云端 API 吗？**  
可以。将 `base_url_anthropic` 指向本地端点（如 Ollama、vLLM、llama.cpp server）。系统使用 Anthropic 兼容的 `/v1/messages` 协议。

**问：如何在 SQLite 和 MySQL 之间切换？**  
修改 `config/settings.yaml` 中的 `database.type`，上层代码使用统一的 `db.py` 接口，无需任何代码改动。

**问：分类过程中 API 调用失败怎么办？**  
失败的条目不标记为已处理，下次流水线运行时会自动重试。

**问：Web 端的报告生成需要多长时间？**  
取决于模型和新闻数量。周报通常 30-90 秒，季度深度报告可能需要 3-5 分钟。前端显示实时进度条，完成后自动跳转。
