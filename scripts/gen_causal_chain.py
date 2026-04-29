#!/usr/bin/env python3
"""
因果链专题分析 — 针对用户指定的关键事件，追溯上游原因和下游影响。

用法:
  python gen_causal_chain.py --id "20260428-cls-hot-003"   # 按新闻ID追踪
  python gen_causal_chain.py --topic "自动驾驶" --months 6  # 按主题追踪
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, insert_report, extract_key_findings
from utils.llm_client import chat_safe
from utils.logging_config import setup_logging

logger = setup_logging("causal_chain", "causal_chain.log")

PROJECT_DIR = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "special"


def find_related_news(keyword: str, months: int = 6) -> list:
    """搜索与关键词相关的所有新闻，按时间排序。"""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")

    news = search_news(
        keyword=keyword,
        date_from=start, date_to=end,
        min_importance=2, limit=100,
    )
    # 按日期升序排列（用于因果链分析）
    news.sort(key=lambda x: x.get("date", ""))
    return news


def format_chain_data(news: list, topic: str) -> str:
    """格式化因果链分析的输入数据。"""
    lines = [
        f"## 分析主题: {topic}",
        f"## 时间范围: 过去6个月",
        f"## 相关新闻数量: {len(news)} 条\n",
        "### 事件时间轴（按日期升序）\n",
    ]

    current_date = ""
    for item in news:
        date = item["date"]
        if date != current_date:
            current_date = date
            lines.append(f"\n### {date}")

        lines.append(
            f"\n**[{item.get('source_name', item['source'])}] {item['title']}**"
        )
        if item.get("ai_summary"):
            lines.append(f"  {item['ai_summary'][:200]}")
        if item.get("ai_why_matters"):
            lines.append(f"  为什么重要: {item['ai_why_matters'][:200]}")

    return "\n".join(lines)


def generate_causal_chain(topic: str, months: int = 6):
    """生成因果链分析报告。"""
    logger.info("Searching news related to '%s'...", topic)
    news = find_related_news(topic, months)

    if len(news) < 5:
        logger.warning("Insufficient related news (%d items), causal chain may be weak", len(news))

    data_text = format_chain_data(news, topic)

    system = """你是顶级的因果推理分析师。基于给定的事件时间轴，构建因果链图谱。

## 分析方法
1. 不只是按时间排列，而是找出真正的因果关系
2. 区分相关性和因果性
3. 标注每个因果链接的确定程度

## 输出结构

### 一、事件全景图
用3-5句话概述这个主题下的核心事件链。

### 二、主因果链
按以下格式构建主因果链：

```
触发事件: [日期] 事件描述
    │
    ├── 因果强度: 强/中/弱
    ▼
中间事件1: [日期] 事件描述
    │
    ├── 因果强度: 强/中/弱
    ▼
中间事件2: [日期] 事件描述
    │
    ├── 因果强度: 强/中/弱
    ▼
当前状态: [日期] 事件描述
    │
    ├── 预测概率: 高/中/低
    ▼
下一阶段可能: [预测] 可能发生什么
```

### 三、支线因果链
与主线并行的次要因果链（至少2条）。

### 四、关键节点人物/机构
谁在推动这个因果链条？列出关键参与方及其角色。

### 五、反事实推理
- 如果某个关键事件没有发生，最可能的不同结局是什么？
- 当前链条中哪个环节最脆弱？一旦断裂会怎样？

### 六、决策启示
- 如果关注这个领域，应该在什么时间窗口做什么决策？
- 有什么信号值得提前布局？

要求：每个因果链接都要有具体的新闻事件支撑。不确定的地方明确标注。"""

    logger.info("Calling LLM to generate causal chain analysis...")
    report = chat_safe(system, [{"role": "user", "content": data_text}], max_tokens=4096)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_topic = topic.replace("/", "-").replace(" ", "_")[:30]
    output_path = REPORTS_DIR / f"causal-chain-{safe_topic}-{datetime.now().strftime('%Y%m%d')}.md"
    header = f"""# 因果链分析报告: {topic}
**数据范围**: 最近{months}个月
**相关新闻**: {len(news)} 条
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
"""
    output_path.write_text(header + report, encoding="utf-8")
    logger.info("Causal chain report saved: %s", output_path)

    # 写入报告索引
    relative_path = str(output_path.relative_to(PROJECT_DIR))
    period = f"causal_{topic[:20]}"
    insert_report("special_causal_chain", period, relative_path, news_count=len(news),
                  key_findings=extract_key_findings(report))
    logger.info("Report index updated")

    return str(output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="因果链专题分析")
    parser.add_argument("--topic", required=True, help="Topic keyword, e.g. '自动驾驶' '中美芯片'")
    parser.add_argument("--months", type=int, default=6, help="Months to look back")
    args = parser.parse_args()

    init_db()
    path = generate_causal_chain(topic=args.topic, months=args.months)
    print(f"\nCausal chain report generated: {path}")
