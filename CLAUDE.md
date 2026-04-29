# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人新闻智能分析系统。从 ModelScope 仓库（`chensongpoixs/daily_news_corpus`）获取每日收集的11个平台新闻，通过 Claude API 自动打标/分类/打分/摘要，存入 SQLite/MySQL 双后端数据库，提供搜索和周期性深度分析报告（周报/月报/季度因果链+机会发现+城市对比）。

## 核心数据流

```
news-corpus/ (git pull 同步)
  → classify.py (Claude Haiku 打标增强，在原 .md 文件顶部插 YAML frontmatter)
  → index_sync.py (同步到数据库)
  → search.py / gen_weekly.py / gen_monthly.py / gen_quarterly.py (查询+分析)
```

新闻增强不改变原始 Markdown 内容，只在文件顶部增量插入 YAML frontmatter。

## 关键命令

```bash
# 环境准备
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."

# 配置校验
python scripts/config_validate.py                # 启动前检查配置和连接

# 一键流水线
python run_pipeline.py                           # 完整流水线（同步→打标→索引→报告）
python run_pipeline.py --classify-limit 50       # 测试模式
python run_pipeline.py --config-only             # 仅校验配置
python run_pipeline.py --skip-report             # 跳过报告生成

# 单独步骤
python scripts/sync_news.py                      # git pull + 检测新文件
python scripts/classify.py --dry-run             # 预览模式
python scripts/classify.py --limit 10            # 仅打标10条（测试）

# 数据库同步
python scripts/index_sync.py                   # 全量重建索引

# 搜索
python scripts/search.py -k "自动驾驶" -c 北京 -i 3 --count
python scripts/search.py -d "经济/金融" --from 2026-04-01 --to 2026-04-28 -n 50

# 分析报告
python scripts/gen_weekly.py                   # 本周周报
python scripts/gen_monthly.py                  # 本月月报
python scripts/gen_quarterly.py --offset -1    # 上一季度深度报告（--offset 0=当前季度）
python scripts/gen_city_compare.py             # 6城市对比分析
python scripts/gen_causal_chain.py --topic "AI芯片" --months 6  # 因果链追踪
```

## 架构要点

### 数据库双后端

`scripts/utils/db.py` 通过 `config/settings.yaml` 中 `database.type` 字段（`sqlite` | `mysql`）透明切换。所有上层代码通过 `init_db()`, `insert_news()`, `search_news()` 等统一接口操作，不感知底层实现。

- SQLite：FTS5 全文搜索，无需额外依赖
- MySQL：FULLTEXT INDEX，需要 `pymysql`，自动建库

### LLM 调用策略

`scripts/utils/llm_client.py` 通过 Anthropic 兼容端点调用模型，支持自动重试（指数退避）和结构化 JSON 输出：

- **`chat()`** — 普通文本对话，report generators 使用
- **`chat_structured()`** — Pydantic 模型校验的 JSON 输出，`classify.py` 使用
- **`chat_safe()`** — 包装了异常捕获的 `chat()`，失败时返回错误文本而非崩溃，所有报告生成脚本使用
- 模型配置在 `config/settings.yaml` 的 `model` 列表中，当前使用第一个模型，通过 `base_url_anthropic` 指定 Anthropic 兼容端点
- 不支持 Anthropic 原生的 prompt caching 和 Batch API（这些功能在非官方端点不可用）

### 分类打标机制

`classify.py` 是核心管线：
1. 扫描 `news-corpus/{YYYYMMDD}/{source}/*.md` 找未增强文件（不以 `---` 开头）
2. 解析原始元数据（来源平台、排名、原文链接、正文）
3. 通过 Pydantic `NewsClassification` 模型做结构化输出
4. 跳过 `is_duplicate=true` 或 `quality_pass=false` 的条目
5. 对通过筛选的文件插入 YAML frontmatter 并更新数据库

### 11个新闻来源差异化

在 `config/source_weight.yaml` 中配置，三个层级：
- **全量处理**（`full_process: true`）：cls-hot、wallstreetcn-hot、thepaper
- **选择性处理**（AI筛选）：toutiao、zhihu、ifeng
- **仅前20条**（`top_only: true`）：weibo、baidu、bilibili、douyin、tieba

### 6城市分析维度

北京/上海/深圳/苏州/南京/淮安，每个城市在 `config/cities.yaml` 中定义了关键词列表和关注方向（Tier 1/2/3）。分类时通过关键词匹配+LLM判断城市关联。

### 季度深度报告

`gen_quarterly.py` 分两阶段：
1. **Sonnet**：按领域分组摘要（科技AI/经济金融/政治国际/社会民生），压缩信息密度
2. **Opus**：接收摘要+完整时间轴，输出6大模块 — 核心叙事线、因果链图谱、底层运行规律、趋势预判、城市竞争、机会地图

报告输出到 `reports/quarterly/{YYYY-Qn}-deep-analysis.md`。

### 配置结构

- `config/settings.yaml`：数据库类型、LLM模型选择、去重阈值、来源策略
- `config/cities.yaml`：6城市关键词（地名+机构名）、Tier、关注维度
- `config/domains.yaml`：4大领域（科技AI/经济金融/政治国际/社会民生）的子领域和关键词
- `config/source_weight.yaml`：11个来源的重要性权重（1-5）、全量/选择性/仅前N
