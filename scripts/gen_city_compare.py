#!/usr/bin/env python3
"""城市对比分析 — 6城市差异化定位+竞争力雷达+人才资本流向。"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, insert_report, extract_key_findings
from utils.config_loader import get_cities
from utils.llm_client import chat_safe
from utils.logging_config import setup_logging

logger = setup_logging("city_compare", "city_compare.log")

PROJECT_DIR = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "special"


def gather_city_news(months: int = 3):
    """收集最近 N 个月各城市的相关新闻。"""
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")

    cities_config = get_cities()
    city_news = {}

    for city in cities_config:
        name = city["name"]
        news = search_news(
            date_from=start, date_to=end,
            city=name, min_importance=2, limit=50,
        )
        city_news[name] = news
        logger.info("%s: %d related news", name, len(news))

    return city_news, start, end


def format_city_data(city_news: dict) -> str:
    """格式化各城市新闻为分析文本。"""
    lines = []
    cities_config = {c["name"]: c for c in get_cities()}

    for name, news in city_news.items():
        cfg = cities_config.get(name, {})
        lines.append(f"\n## {name} (Tier {cfg.get('tier', '?')})")
        lines.append(f"关注方向: {', '.join(cfg.get('focus_areas', []))}")

        if not news:
            lines.append("> 近期无相关重要新闻\n")
            continue

        for item in news[:20]:
            lines.append(f"\n- **[{item['date']}] ★{item['importance']}** {item['title']}")
            if item.get('ai_summary'):
                lines.append(f"  {item['ai_summary'][:150]}")
    return "\n".join(lines)


def generate_city_compare(months: int = 3):
    """生成城市对比分析报告。"""
    logger.info("Collecting city news (last %d months)...", months)
    city_news, start, end = gather_city_news(months)
    data_text = format_city_data(city_news)

    cities_config = get_cities()
    city_names = [c["name"] for c in cities_config]

    system = f"""你是城市竞争力分析专家。基于以下新闻数据，对 {', '.join(city_names)} 做对比分析。

## 报告结构

### 一、差异化定位分析
每个城市的核心战略方向是什么？（基于新闻中反映的实际行动，不是纸面上的定位）
哪些城市在正面竞争？哪些城市互补？

### 二、竞争力雷达评估
对每个城市在以下维度打分（1-10），并给出评分依据：

| 城市 | 政策力度 | 资本活跃度 | 人才吸引力 | 产业基础 | 创新活力 | 综合 |
|------|---------|-----------|-----------|---------|---------|------|
{chr(10).join(f'| {c["name"]} | - | - | - | - | - | - |' for c in cities_config)}

### 三、人才/资本流动推断
从新闻中推断人才和资本在6个城市间的实际流向。
- 哪些城市在吸引人才？（有什么具体政策/事件支撑）
- 哪些城市的资本活跃度在上升/下降？

### 四、发展时差分析
- 苏州/南京 相比 京沪深 落后多少？它们在复制先行者的路径吗？
- 淮安 处于什么发展阶段？产业承接的具体信号有哪些？

### 五、个人策略建议
- 如果考虑职业发展，每个城市适合什么类型的人？
- 如果考虑投资/创业，每个城市现在的窗口在哪里？
- 哪个城市可能是未来3-5年的"洼地"？

要求：基于新闻事实，不做空泛判断。"""

    logger.info("Calling LLM to generate city comparison...")
    report = chat_safe(system, [{"role": "user", "content": data_text}], max_tokens=4096)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"city-comparison-{datetime.now().strftime('%Y%m%d')}.md"
    header = f"""# 城市对比分析报告
**数据周期**: {start} ~ {end}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---
"""
    output_path.write_text(header + report, encoding="utf-8")
    logger.info("City comparison report saved: %s", output_path)

    # 写入报告索引
    total_news = sum(len(v) for v in city_news.values())
    relative_path = str(output_path.relative_to(PROJECT_DIR))
    period = f"{start}_{end}"
    insert_report("special_city_compare", period, relative_path, news_count=total_news,
                  key_findings=extract_key_findings(report))
    logger.info("Report index updated")

    return str(output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="城市对比分析")
    parser.add_argument("--months", type=int, default=3, help="Months to look back (default: 3)")
    args = parser.parse_args()
    init_db()
    path = generate_city_compare(months=args.months)
    print(f"\nCity comparison report generated: {path}")
