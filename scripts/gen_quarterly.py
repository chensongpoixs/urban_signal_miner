#!/usr/bin/env python3
"""
季度深度报告生成 — 系统的核心产出。

分析内容：
1. 核心叙事线 — 这个季度的主题
2. 因果链图谱 — 事件A→事件B→事件C
3. 底层运行规律 — 从新闻表象提炼社会/经济/政治的规律
4. 趋势识别与预判
5. 城市竞争态势
6. 机会地图 — 投资/职业/商业机会
7. 信息盲区

使用 Claude Opus 分块处理，避免 token 超限。
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, get_source_stats, insert_report, extract_key_findings
from utils.config_loader import get_cities
from utils.llm_client import chat_safe, chat
from utils.logging_config import setup_logging

logger = setup_logging("quarterly", "quarterly.log")

PROJECT_DIR = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "quarterly"


def get_quarter_range(offset: int = 0) -> tuple[str, str, str]:
    """返回某个季度的 (quarter_key, start_date, end_date)。
    offset=0 是当前季度，-1 是上一季度。
    """
    today = datetime.now()
    # 调整到目标季度的第一个月
    current_q = (today.month - 1) // 3  # 0,1,2,3
    target_q = current_q + offset  # 按季度偏移

    year = today.year + (target_q // 4)
    q = target_q % 4
    first_month = q * 3 + 1

    start = datetime(year, first_month, 1)
    if q == 3:  # Q4
        end = datetime(year, 12, 31)
    else:
        end_month = first_month + 2
        end = datetime(year, end_month + 1, 1) - timedelta(days=1)

    quarter_key = f"{year}-Q{q+1}"
    return quarter_key, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def gather_quarterly_news(start: str, end: str) -> list:
    """收集季度内所有重要性>=2的新闻，按时间排序。"""
    return search_news(
        date_from=start, date_to=end,
        min_importance=2, limit=300,
    )


def build_timeline(news: list) -> str:
    """构建事件时间轴文本。"""
    lines = [f"## 季度新闻时间轴（共 {len(news)} 条）\n"]

    current_date = ""
    for item in news:
        date = item['date']
        if date != current_date:
            current_date = date
            lines.append(f"\n### {date}\n")

        cities = item.get('cities', [])
        city_str = f" [{','.join(cities)}]" if cities else ""
        importance = item.get('importance', 0)

        lines.append(
            f"**[★{importance}] {item['title']}**\n"
            f"- 来源: {item.get('source_name', item['source'])} | 领域: {', '.join(item.get('domain', []))}\n"
            f"- 标签: {', '.join(item.get('tags', []))}{city_str}\n"
            f"- {item.get('ai_summary', '无摘要')}\n"
        )
        if item.get('ai_why_matters') and importance >= 3:
            lines.append(f"- 重要性: {item['ai_why_matters'][:200]}\n")

    return "\n".join(lines)


def run_phase1_summary(timeline: str) -> str:
    """阶段1：按领域分组摘要。Sonnet 预提炼各领域关键事件。"""
    logger.info("Phase 1: domain summary")

    system = """你是专业新闻分析师。下面是一个季度的新闻时间轴。
请按领域分别总结本季度各领域的关键事件和发展趋势。

领域包括：科技/AI、经济/金融、政治/国际关系、社会/民生

每个领域输出：
1. 本领域TOP 5-10 关键事件（按时间排列）
2. 本领域的主要趋势方向
3. 与其他领域的交叉点

输出简洁，每个领域控制在 500 字以内。"""

    summary = chat_safe(
        system,
        [{"role": "user", "content": f"季度新闻时间轴：\n\n{timeline[:15000]}"}],
        model_key="fast", max_tokens=4096,
    )
    return summary


def run_phase2_deep_analysis(timeline: str, phase1_summary: str) -> str:
    """阶段2：深度分析 — 因果链 + 底层规律 + 机会地图。用 Opus。"""
    logger.info("Phase 2: deep analysis")

    cities_config = get_cities()
    city_info = "\n".join(
        f"- **{c['name']}** (Tier {c['tier']}): {', '.join(c['focus_areas'])}"
        for c in cities_config
    )

    system = f"""你是顶级战略分析师和社会科学家。基于一个季度的新闻数据，做深度分析。

## 城市关注维度
{city_info}

## 报告结构

### 一、本季度的核心叙事线
如果这个季度是一本书，它的3-5条主题叙事是什么？每条用一句话概括，然后展开100-200字解释。

### 二、因果链图谱
构建本季度最重要的因果链（至少5条）。每条格式：

```
链条名称: "XXX → YYY → ZZZ"

[日期A] 事件A
[日期B] 事件B
[日期C] 事件C

推导逻辑: A如何导致B，B如何导致C
证据: 引用具体的新闻标题和日期
不确定性: 这个链条中哪个环节最脆弱？有替代解释吗？
趋势方向: ████████░░ (加速中 / 已完成 / 可能在下一阶段反转)
```

### 三、底层运行规律
从本季度新闻中提炼出反复出现的社会/经济/政治运行规律（至少5条）。

每条规律格式：
- **规律名称**（一句话）
- **新闻证据**：引用至少3个季度内具体事件
- **规律解释**：这条规律揭示了怎样的运行机制？
- **适用范围与边界**：在什么条件下成立？什么时候会失效？
- **可操作洞察**：理解这条规律对个人有什么用？

### 四、趋势识别与预判
- **加速中的趋势**（列出3-5项，每项含证据事件）
- **减速/可能终结的趋势**（列出3-5项）
- **下个季度可能的拐点事件**（列出3-5项预测）

### 五、城市竞争态势
对北京/上海/深圳/苏州/南京/淮安做对比分析：
- 本季度各城市的关键动态
- 人才/资本/产业的实际流向（从新闻中推断，不凭空猜测）
- 城市间的竞争（谁在抢谁的市场/人才）和协作
- 发展时差分析：后发城市是否在复制先行城市的路径？

### 六、机会地图
从本季度趋势中识别机会：

**投资机会**
| 方向 | 驱动力 | 置信度 | 时间窗口 | 风险 |
|------|--------|--------|----------|------|

**职业机会**
| 领域/城市 | 信号 | 置信度 | 技能需求 |
|-----------|------|--------|----------|

**商业机会**
| 方向 | 市场空白 | 置信度 | 进入门槛 |
|------|----------|--------|----------|

### 七、信息盲区与建议
- 本季度哪些重要问题缺乏足够信息？
- 下季度建议重点收集哪类信息？
- 当前的新闻源有什么缺失？

---

重要要求：
1. 所有论断必须引用具体的新闻事件作为证据
2. 因果链条必须标注不确定性
3. 机会必须给出置信度和风险
4. 不要泛泛而谈，要有实质内容
5. 不要求字数上限，追求深度和质量
"""

    prompt = f"""以下是一个季度的新闻数据，请做深度分析。

## 领域摘要（由前一轮分析生成）
{phase1_summary[:4000]}

## 完整新闻时间轴
{timeline[:25000]}

请按照指定的报告结构输出完整的季度深度分析报告。"""

    report = chat_safe(
        system,
        [{"role": "user", "content": prompt}],
        model_key="deep", max_tokens=8192,
    )
    return report


def generate_quarterly(offset: int = 0):
    """生成季度深度报告。offset=0 为当前季度，-1 为上一季度。"""
    quarter_key, start, end = get_quarter_range(offset)
    logger.info("Generating quarterly report: %s (%s ~ %s)", quarter_key, start, end)

    init_db()
    news = gather_quarterly_news(start, end)
    logger.info("Found %d news items", len(news))

    if len(news) < 20:
        logger.warning("Insufficient news (%d items), analysis quality may be affected", len(news))

    # 构建时间轴
    timeline = build_timeline(news)

    # 阶段1：领域摘要
    try:
        phase1_summary = run_phase1_summary(timeline)
    except Exception as e:
        logger.warning("Phase 1 (domain summary) failed, degraded to direct deep analysis: %s", e)
        phase1_summary = ""

    # 阶段2：深度分析
    report = run_phase2_deep_analysis(timeline, phase1_summary)

    # 分析质量标注
    degraded = "（含领域摘要）" if phase1_summary else "（降级：跳过领域摘要）"
    # 保存
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"{quarter_key}-deep-analysis.md"

    header = f"""# {quarter_key} 季度深度分析报告
**周期**: {start} ~ {end}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**新闻数量**: {len(news)} 条
**分析方法**: 两阶段分析 {degraded}

---
"""
    output_path.write_text(header + report, encoding="utf-8")
    logger.info("Quarterly report saved: %s", output_path)

    # 写入报告索引
    relative_path = str(output_path.relative_to(PROJECT_DIR))
    insert_report("quarterly", quarter_key, relative_path, news_count=len(news),
                  key_findings=extract_key_findings(report))
    logger.info("Report index updated")

    return str(output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成季度深度分析报告")
    parser.add_argument("--offset", type=int, default=0,
                        help="Quarter offset: 0=current quarter, -1=previous")
    args = parser.parse_args()
    path = generate_quarterly(offset=args.offset)
    print(f"\nQuarterly deep report generated: {path}")
