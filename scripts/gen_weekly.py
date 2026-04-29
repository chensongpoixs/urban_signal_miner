#!/usr/bin/env python3
"""周报生成 — 聚合本周重要新闻，AI 分析趋势信号。"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, insert_report, extract_key_findings
from utils.llm_client import chat_safe
from utils.logging_config import setup_logging

logger = setup_logging("weekly", "weekly.log")

PROJECT_DIR = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "weekly"


def get_week_range(week_str: str = None) -> tuple[str, str, str]:
    """Returns (week_key, start_date, end_date). If week_str is given, parse as YYYY-WNN."""
    if week_str:
        # Parse "YYYY-WNN" format
        import re
        m = re.match(r"^(\d{4})-W(\d{2})$", week_str)
        if not m:
            raise ValueError(f"Invalid week format: {week_str}, expected YYYY-WNN")
        year = int(m.group(1))
        week = int(m.group(2))
        from datetime import date
        # Monday of the given ISO week
        jan4 = date(year, 1, 4)
        monday = jan4 - timedelta(days=jan4.isoweekday() - 1) + timedelta(weeks=week - 1)
        sunday = monday + timedelta(days=6)
        week_key = f"{year}-W{week:02d}"
        return week_key, monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    week_key = f"{monday.year}-W{monday.isocalendar()[1]:02d}"
    return week_key, monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def gather_news(start: str, end: str) -> str:
    """收集本周新闻，格式化为分析用的文本。"""
    # 高重要性新闻
    top = search_news(date_from=start, date_to=end, min_importance=3, limit=50)

    if not top:
        logger.warning("No news with importance >= 3 this week")
        return "本周无重要新闻。"

    lines = [f"## 本周新闻（{start} ~ {end}），共 {len(top)} 条高重要性新闻\n"]
    lines.append("按日期+重要性排序：\n")

    for item in top:
        lines.append(f"""
### {item['date']} | ★{item['importance']} | [{item.get('source_name', item['source'])}] {item['title']}
- 标签：{', '.join(item.get('tags', []))}
- 领域：{', '.join(item.get('domain', []))}
- 城市：{', '.join(item.get('cities', []))}
- 摘要：{item.get('ai_summary', '无')}
- 为何重要：{item.get('ai_why_matters', '无')}
""")

    return "\n".join(lines)


def generate_weekly(week_str: str = None):
    """生成周报并保存到 reports/weekly/。week_str 如 '2026-W17'，None 为本周。"""
    week_key, start, end = get_week_range(week_str)
    logger.info("Generating weekly report: %s (%s ~ %s)", week_key, start, end)

    init_db()
    news_text = gather_news(start, end)

    system = """你是一位资深战略分析顾问。请基于本周的重要新闻，生成一份精炼的周报。

## 报告结构

### 一、本周 TOP 10 事件
按重要性排序，每条约80字说明为什么重要。

### 二、领域动态
分别总结以下领域的本周关键动态（每个领域2-3句话）：
- 科技/AI
- 经济/金融
- 政治/国际关系
- 社会/民生

### 三、趋势信号
- **加速中的趋势**：哪些趋势本周获得了多个事件的印证？
- **减速/转向的趋势**：哪些之前的热门方向出现降温？
- **本周新出现的信号**：有什么之前没关注到的新动向？

### 四、城市动态追踪
对以下城市各写一段（仅限本周有相关新闻的城市，没有则跳过）：
北京 / 上海 / 深圳 / 苏州 / 南京 / 淮安

### 五、机会提示
本周新闻中隐含的投资/职业/商业机会（如果确实有值得关注的）。

### 六、下周关注点
预测下周可能的重要事件或数据发布。

---

总字数控制在 1500-2000 字。每个论断都要引用具体事件。"""

    prompt = f"以下是本周 ({start} ~ {end}) 的重要新闻合集，请生成周报：\n\n{news_text}"
    logger.info("Calling LLM to generate weekly report...")
    report = chat_safe(system, [{"role": "user", "content": prompt}], max_tokens=4096)

    # 保存报告
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"{week_key}-report.md"
    header = f"""# 每周新闻分析报告
**周期**: {start} ~ {end}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**周期编号**: {week_key}

---
"""
    output_path.write_text(header + report, encoding="utf-8")
    logger.info("Weekly report saved: %s", output_path)

    # 写入报告索引
    relative_path = str(output_path.relative_to(PROJECT_DIR))
    news_count = len(search_news(date_from=start, date_to=end, min_importance=3, limit=200))
    insert_report("weekly", week_key, relative_path, news_count=news_count,
                  key_findings=extract_key_findings(report))
    logger.info("Report index updated")

    return str(output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate weekly report")
    parser.add_argument("--week", default=None, help="Week to generate (YYYY-WNN), default: current week")
    args = parser.parse_args()
    path = generate_weekly(week_str=args.week)
    print(f"\nWeekly report generated: {path}")
