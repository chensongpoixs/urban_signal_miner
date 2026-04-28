#!/usr/bin/env python3
"""月报生成 — 月度趋势确认 + 跨领域关联 + 城市对比。"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, get_source_stats
from utils.llm_client import chat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "monthly.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "monthly"


def get_month_range() -> tuple[str, str, str]:
    """返回本月的 (month_key, start_date, end_date)。"""
    today = datetime.now()
    first_day = today.replace(day=1)
    # 下月第一天减一天 = 本月最后一天
    if today.month == 12:
        last_day = today.replace(year=today.year + 1, month=1, day=1)
    else:
        last_day = today.replace(month=today.month + 1, day=1)
    last_day = last_day - __import__('datetime').timedelta(days=1)
    month_key = f"{today.year}-{today.month:02d}"
    return month_key, first_day.strftime("%Y-%m-%d"), last_day.strftime("%Y-%m-%d")


def gather_news(start: str, end: str) -> str:
    """收集本月高重要性新闻。"""
    top = search_news(date_from=start, date_to=end, min_importance=3, limit=100)
    if not top:
        return "本月无重要新闻。"

    # 来源统计
    stats = get_source_stats(start, end)

    lines = [f"## 本月新闻概览（{start} ~ {end}），共 {len(top)} 条高重要性新闻\n"]

    lines.append("### 来源统计")
    for s in stats:
        lines.append(f"- {s.get('source_name', s['source'])}: {s['cnt']} 条，平均重要性 {s['avg_imp']:.1f}")
    lines.append("")

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


def generate_monthly():
    """生成月报。"""
    month_key, start, end = get_month_range()
    logger.info("生成月报: %s (%s ~ %s)", month_key, start, end)

    init_db()
    news_text = gather_news(start, end)

    # 尝试加载本月周报做交叉参考
    weekly_dir = PROJECT_DIR / "reports" / "weekly"
    weekly_context = ""
    if weekly_dir.exists():
        weekly_files = sorted(weekly_dir.glob(f"*{month_key[:4]}-*.md"))
        for wf in weekly_files:
            try:
                weekly_context += f"\n{wf.read_text(encoding='utf-8')[:2000]}\n"
            except Exception:
                pass

    system = """你是资深战略分析师。基于本月重要新闻，生成深度月报。

## 报告结构

### 一、本月核心叙事
本月最重要的3-5条主题叙事，每条用50字概括。

### 二、月度趋势确认
对比本月各周新闻，回答：
- 哪些趋势得到了持续强化？（多周/多事件印证）
- 哪些之前的热门信号被证伪或降温？
- 什么新趋势在月末出现？

### 三、跨领域关联图谱
找出科技→金融、政策→产业、国际→国内等跨领域传导链条。

### 四、城市月度对比
6个城市本月各自的亮点和变化（有新闻则写，无新闻则跳过），
城市间的竞争/合作关系变化。

### 五、关键实体月度动态
本月最活跃的公司/机构/人物，按条列出其动向。

### 六、月度机会扫描
本月新出现的或得到强化的投资/职业/商业机会。

### 七、下月前瞻
预测下月可能的关键事件和政策节点。

---

总字数控制在 2500-3500 字。每个论断引用具体新闻事件。"""

    prompt = f"本月重要新闻：\n\n{news_text}"
    if weekly_context:
        prompt += f"\n\n本月周报参考：\n{weekly_context}"

    logger.info("调用 Claude 生成月报...")
    report = chat(system, [{"role": "user", "content": prompt}], max_tokens=8192)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"{month_key}-report.md"
    header = f"""# 月度新闻分析报告
**周期**: {start} ~ {end}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**月度编号**: {month_key}

---
"""
    output_path.write_text(header + report, encoding="utf-8")
    logger.info("月报已保存: %s", output_path)
    return str(output_path)


if __name__ == "__main__":
    path = generate_monthly()
    print(f"\n月报已生成: {path}")
