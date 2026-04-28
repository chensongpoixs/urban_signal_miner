# Urban Signal Miner

城市信号挖掘系统 — 从海量新闻中提炼趋势、因果链与机会信号。

## 一句话定位

每天自动收集11个平台的新闻，用 AI 打标分类后存入数据库，定期生成深度分析报告——**因果链追踪 + 底层规律挖掘 + 城市竞争对比 + 机会发现**。

## 数据来源

数据托管在 [ModelScope](https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus)，每日更新，覆盖11个平台：

| 层级 | 来源 | 说明 |
|------|------|------|
| 重点分析 | 财联社(cls-hot)、华尔街见闻(wallstreetcn-hot)、澎湃(thepaper) | 财经/政经全量精标 |
| 筛选分析 | 今日头条(toutiao)、知乎(zhihu)、凤凰网(ifeng) | AI筛选高价值内容 |
| 热度感知 | 微博(weibo)、百度(baidu)、B站(bilibili)、抖音(douyin)、贴吧(tieba) | 仅取Top20感知舆情 |

## 分析体系

### 三层报告节奏

```
周报（Sonnet）→ 月报（Sonnet）→ 季度深度报告（Opus 两阶段）
   TOP10事件         趋势确认           因果链图谱
   趋势信号          跨领域关联          底层运行规律
   城市动态          月度城市对比        趋势预判
   机会提示                              城市竞争态势
                                        机会地图
```

### 季度深度报告6大模块

1. **核心叙事线** — 这个季度的3-5条主题叙事
2. **因果链图谱** — 事件A→事件B→事件C，含推导逻辑和新闻证据
3. **底层运行规律** — 从新闻表象提炼社会/经济/政治机制
4. **趋势识别与预判** — 加速/减速/拐点
5. **城市竞争态势** — 京沪深苏南淮6城差异化分析
6. **机会地图** — 投资/职业/商业机会，含置信度与时间窗口

### 6城市追踪

| 城市 | 定位 | Tier |
|------|------|------|
| 北京 | 政策先行先试 + 科创中心 | 1 |
| 上海 | 国际金融中心 + 集成电路/生物医药 | 1 |
| 深圳 | 硬件制造 + 出海 + 低空经济 | 1 |
| 苏州 | 高端制造 + 外资经济 | 2 |
| 南京 | 科教资源 + 软件信息服务 | 2 |
| 淮安 | 产业承接/转移 + 苏北振兴 | 3 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 API Key
export ANTHROPIC_API_KEY="sk-ant-..."

# 3. 同步数据
python scripts/sync_news.py

# 4. AI 打标（首次建议先试几条）
python scripts/classify.py --limit 10 --dry-run   # 预览
python scripts/classify.py --limit 10              # 正式
python scripts/classify.py                          # 全量

# 5. 搜索
python scripts/search.py -k "自动驾驶" -c 北京 -i 3

# 6. 生成报告
python scripts/gen_weekly.py
python scripts/gen_monthly.py
python scripts/gen_quarterly.py
python scripts/gen_city_compare.py
python scripts/gen_causal_chain.py --topic "AI芯片"
```

## 目录结构

```
urban_signal_miner/
├── config/
│   ├── settings.yaml          # 全局配置（数据库类型、LLM模型、去重阈值）
│   ├── cities.yaml            # 6城市关键词与关注维度
│   ├── domains.yaml           # 4大领域分类体系
│   └── source_weight.yaml     # 11个来源重要性权重
├── news-corpus/               # ModelScope 数据本地镜像（git clone）
├── scripts/
│   ├── sync_news.py           # git pull 同步
│   ├── classify.py            # AI 打标增强（核心管线）
│   ├── index_sync.py          # 全量索引重建
│   ├── search.py              # 命令行多维搜索
│   ├── gen_weekly.py          # 周报
│   ├── gen_monthly.py         # 月报
│   ├── gen_quarterly.py       # 季度深度报告（Opus两阶段）
│   ├── gen_city_compare.py    # 城市对比分析
│   ├── gen_causal_chain.py    # 因果链专题
│   └── utils/
│       ├── llm_client.py      # Claude API 封装
│       ├── db.py              # MySQL/SQLite 双后端
│       └── config_loader.py   # YAML 配置读取
├── reports/                   # 生成的报告
├── db/                        # 数据库文件
└── logs/                      # 运行日志
```

## 数据库配置

在 `config/settings.yaml` 中切换 `database.type`：

```yaml
database:
  type: "sqlite"   # 或 "mysql"
  sqlite:
    path: "db/news.db"
  mysql:
    host: "127.0.0.1"
    port: 3306
    user: "root"
    password: ""
    database: "daily_news"
    charset: "utf8mb4"
```

上层代码零改动，`db.py` 自动透明切换。

## 成本预估

- 日常打标（Haiku）：约 $5/天（~600条全量）
- 周报（Sonnet）：约 $0.50/次
- 月报（Sonnet）：约 $2/次
- 季度深度报告（Opus 两阶段）：约 $8/次

月度总成本约 $15-25，开启 Batch API 可再省50%。

## 依赖

- Python 3.10+
- `anthropic` — Claude API SDK
- `pyyaml` — 配置解析
- `pydantic` — 结构化输出校验
- `pymysql` — MySQL 后端（仅 MySQL 模式需要）
