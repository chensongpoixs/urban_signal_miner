# Urban Signal Miner

**城市信号挖掘系统** — 11源新闻聚合 × AI增强 × 多维分析 × 机会发现

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> 一套生产级的新闻情报管线：每日自动接入 11 个中文平台新闻，通过 AI 对每条新闻进行领域分类、实体提取、重要性打分、因果影响评估，存入双后端数据库（SQLite/MySQL，支持全文检索），并按节奏产出多层次分析报告——从周度趋势简报到季度因果链深度图谱。

---

## 快速开始

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

python run_pipeline.py                           # 一键流水线：同步→打标→索引→报告
python scripts/search.py -k "AI芯片" -c 深圳 -i 4  # 多维度搜索
python scripts/gen_quarterly.py --offset -1       # 上一季度深度报告
```

**输入**：每日 600–900 条原始 Markdown 新闻（11 个平台）  
**产出**：结构化新闻索引 + 周报/月报/季度深度报告（含因果链、趋势信号、城市竞争力、机会地图）  
**成本**：本地模型几乎为零；云端 API 约 $15–25/月

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
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      分析报告层                                      │
│                                                                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────────────────┐  │
│  │  周报    │───▶│  月报    │───▶│         季度深度报告           │  │
│  │ (快模型) │    │ (快模型) │    │  阶段1: 领域摘要 (快模型)      │  │
│  │  TOP10   │    │  趋势确认 │    │  阶段2: 因果推理 (深模型)      │  │
│  │  趋势信号 │    │  跨域关联 │    │  六大模块全景图谱              │  │
│  └──────────┘    └──────────┘    └──────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────┐  ┌──────────────────────────────────────┐  │
│  │    城市对比分析     │  │          因果链追踪                   │  │
│  │  6城竞争力雷达      │  │  上游原因追溯 → 下游影响预测          │  │
│  │  人才/资本流向      │  │  带置信度标注的因果链路图              │  │
│  └────────────────────┘  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心设计决策

| 决策 | 理由 |
|------|------|
| **YAML frontmatter 注入**（而非独立元数据文件） | 无损增强：原始 Markdown 完整保留；元数据随内容走；单一数据源 |
| **数据库双后端**（SQLite ↔ MySQL） | 个人使用零配置 SQLite；多进程/并发场景切换 MySQL；`db.py` 统一接口，上层零改动 |
| **季度报告两阶段分析** | 快模型将 300+ 条新闻压缩为领域摘要；深模型基于压缩后的上下文做推理——既突破 token 上限，又不丢失关键信号 |
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
| `source` | VARCHAR(32) | ✓ | 来源标识（如 `cls-hot`） |
| `source_name` | VARCHAR(64) | | 来源显示名（如 `财联社电报`） |
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

### 季度深度报告六大模块

| # | 模块 | 方法 |
|---|------|------|
| 1 | **核心叙事线** | 将本季度事件凝练为 3–5 条主题故事线 |
| 2 | **因果链图谱** | 事件A→事件B→事件C，含推导逻辑、新闻证据（具体标题+日期）、不确定性标注 |
| 3 | **底层运行规律** | 从新闻表象提炼反复出现的社会/经济/政治运行机制，每条规律≥3个具体事件佐证，标注适用范围与边界条件 |
| 4 | **趋势识别与预判** | 加速趋势、减速趋势、下季度潜在拐点事件 |
| 5 | **城市竞争态势** | 6城政策力度/资本活跃度/人才吸引力/产业基础/创新活力雷达，基于实际新闻推断资源流向 |
| 6 | **机会地图** | 投资/职业/商业机会，附置信度与时间窗口 |

---

## 命令参考

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
python scripts/classify.py --dry-run             # 预览模式（不实际修改文件）
python scripts/classify.py --limit 10            # 仅处理10条（测试用）
python scripts/classify.py                       # 处理全部待处理文件
python scripts/classify.py --files a.md b.md     # 仅处理指定文件

# 索引同步
python scripts/index_sync.py                     # 全量重建索引
python scripts/index_sync.py --incremental       # 仅同步新文件

# 配置校验
python scripts/config_validate.py                # 启动前配置检查
```

### 搜索

```bash
# 全文搜索 + 多维筛选
python scripts/search.py -k "自动驾驶"                            # 关键词搜索
python scripts/search.py -k "半导体" -c 上海 -i 4                 # 城市 + 重要性
python scripts/search.py -d "经济/金融" --from 2026-04-01         # 领域 + 日期范围
python scripts/search.py -k "AI" -s cls-hot -n 50                 # 来源 + 条数限制

# 输出格式
python scripts/search.py -k "芯片" --format json                   # JSON 输出
python scripts/search.py -k "芯片" --format csv -o results.csv     # 导出 CSV
python scripts/search.py -k "芯片" --count                         # 仅显示计数
```

### 报告生成

```bash
# 周期性报告
python scripts/gen_weekly.py                      # 本周周报
python scripts/gen_weekly.py --week 2026-W15      # 历史周报
python scripts/gen_monthly.py                     # 本月月报
python scripts/gen_monthly.py --month 2026-03     # 历史月报
python scripts/gen_quarterly.py                   # 当前季度
python scripts/gen_quarterly.py --offset -1       # 上一季度

# 专题报告
python scripts/gen_city_compare.py                # 6城市对比（近3个月）
python scripts/gen_city_compare.py --months 6     # 扩展时间窗口
python scripts/gen_causal_chain.py --topic "AI芯片"               # 因果链追踪
python scripts/gen_causal_chain.py --topic "房价" --months 12     # 一年回溯
```

---

## 配置说明

### `config/settings.yaml` — 全局配置

```yaml
project:
  news_dir: "news-corpus"           # ModelScope 仓库本地路径

model:
  - name: "Local-Fast"
    role: "fast"                    # 用途: classify, weekly, monthly, quarterly-phase1
    base_url_anthropic: "http://localhost:11434"
    api_key: ""                     # 留空则从环境变量 ANTHROPIC_API_KEY 读取
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 15000
    max_retries: 1

  - name: "Local-Deep"
    role: "deep"                    # 用途: quarterly-phase2, causal-chain
    base_url_anthropic: "http://localhost:11434"
    api_key: ""
    model: "gemma-4-26B-it-Q4_K_M"
    timeout: 30000
    max_retries: 1

llm_limits:
  classify_max_tokens: 2048
  classify_batch_size: 30          # 每批处理条数
  classify_interval_seconds: 1     # API 调用间隔（防限流）
  classify_body_chars: 3000        # 正文截断字符数
  weekly_max_tokens: 4096
  monthly_max_tokens: 8192
  quarterly_max_tokens: 8192
  special_max_tokens: 4096

dedup:
  title_similarity_threshold: 0.8  # 标题相似度阈值（超过视为重复）

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
```

### `config/cities.yaml`

6 城市各定义 `keywords`（地名 + 机构名，用于打标前预筛）和 `focus_areas`（关注维度）。`classify.py` 在调用 LLM 之前先用关键词做字符串匹配，匹配到的城市列表注入 prompt，缩小候选范围、降低 API 成本。

### `config/domains.yaml`

4 大领域（科技/AI、经济/金融、政治/国际关系、社会/民生）各含子领域与关键词，用于 AI 分类指引。

### `config/source_weight.yaml`

11 个来源的 `weight`（1–5）、`full_process`（是否全量处理）、`top_only`（仅取前20条）。

---

## 部署方案

### 本地个人使用

```bash
# 环境准备
pip install -r requirements.txt

# 克隆新闻语料库
git clone https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus.git news-corpus

# 运行流水线
python run_pipeline.py
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

### 生产环境注意事项

- **数据库**：多进程/并发场景建议用 MySQL；双后端架构保证切换零代码改动
- **模型端点**：`role: "fast"` 和 `role: "deep"` 分开配置。生产环境建议深度分析用云端高端模型，日常打标用本地/廉价端点
- **日志管理**：所有日志使用 `RotatingFileHandler`（单文件 10MB，保留 5 个备份），存放在 `logs/` 目录
- **断点续跑**：`processed_files` 表保证打标任务中断后可续跑。失败的条目不标记已处理，下次自动重试
- **速率控制**：`classify_interval_seconds` 防止 API 限流

---

## 开发指南

### 目录结构

```
daily/
├── config/                  # YAML 配置文件
├── news-corpus/             # ModelScope 数据本地镜像
├── scripts/
│   ├── sync_news.py         # 第1步：git pull 同步
│   ├── classify.py          # 第2步：AI 增强打标（核心管线）
│   ├── index_sync.py        # 第3步：数据库索引同步
│   ├── search.py            # 命令行搜索工具
│   ├── gen_weekly.py        # 周报生成
│   ├── gen_monthly.py       # 月报生成
│   ├── gen_quarterly.py     # 季度深度报告（两阶段分析）
│   ├── gen_city_compare.py  # 城市对比专题
│   ├── gen_causal_chain.py  # 因果链专题
│   ├── config_validate.py   # 启动前配置校验
│   └── utils/
│       ├── db.py            # 数据库抽象层（SQLite/MySQL 双后端）
│       ├── llm_client.py    # LLM API 封装（Anthropic 兼容端点）
│       ├── config_loader.py # YAML 配置读取
│       ├── file_utils.py    # 文件扫描工具
│       └── logging_config.py # 统一日志配置（RotatingFileHandler）
├── run_pipeline.py          # 一键流水线编排器
├── reports/                 # 生成的分析报告
│   ├── weekly/
│   ├── monthly/
│   ├── quarterly/
│   └── special/
├── db/                      # SQLite 数据库文件
├── logs/                    # 运行日志（10MB × 5 轮转）
└── docs/                    # 文档
```

### 关键设计模式

**数据库双后端**：`_DB` 类根据 `settings.yaml` 初始化 SQLite 或 MySQL。所有公开函数（`insert_news()`、`search_news()` 等）在不同后端下行为一致。`execute()` 自动完成占位符转换（`?` → `%s`）。

**安全 LLM 包装**：`chat_safe()` 捕获所有异常并返回错误文本而非崩溃——报告生成器必须在 API 失败时仍能产出结果。

**无损增强**：`classify.py` 在原 Markdown 文件顶部添加 YAML frontmatter，原始内容完整保留在 `---` 分隔线下。重复运行安全（已有 frontmatter 的文件自动跳过）。

**断点续跑**：无论新闻通过质量筛选还是被跳过，处理完立即写入 `processed_files`。重启时跳过已处理文件，零重复 API 开销。

---

## 依赖

| 包 | 用途 |
|----|------|
| `anthropic` | Claude/Anthropic 兼容端点 API 客户端 |
| `pyyaml` | 配置文件解析 |
| `pydantic` | AI 分类的结构化输出校验 |
| `pymysql` | MySQL 后端（仅 `database.type: mysql` 时需要） |
| `tqdm` | 批量打标的进度条 |

Python 3.10+ 运行环境。

---

## 常见问题

**问：能用本地 LLM 替代云端 API 吗？**  
可以。将 `base_url_anthropic` 指向本地端点（如 Ollama、vLLM、llama.cpp server）。系统使用 Anthropic 兼容的 `/v1/messages` 协议。建议配置两个模型条目分别标注 `role: "fast"` 和 `role: "deep"` 以优化成本。

**问：如何在 SQLite 和 MySQL 之间切换？**  
修改 `config/settings.yaml` 中的 `database.type`，上层代码使用统一的 `db.py` 接口，无需任何代码改动。MySQL 表结构自动创建，字符集为 `utf8mb4`。

**问：分类过程中 API 调用失败怎么办？**  
失败的条目不标记为已处理，下次流水线运行时会自动重试。同批次其他条目继续正常处理。进度条会显示成功/失败情况。

**问：能否补生成历史报告？**  
可以。周报支持 `--week 2026-W15`，月报支持 `--month 2026-03`。季度报告使用 `--offset`（0=当前季度，-1=上一季度，-2=两个季度前，以此类推）。
