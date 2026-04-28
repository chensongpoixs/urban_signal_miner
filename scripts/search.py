#!/usr/bin/env python3
"""命令行新闻搜索工具。"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, count_news
from utils.config_loader import get_cities


def format_results(results, total: int, offset: int = 0) -> str:
    """格式化搜索结果。"""
    lines = []
    lines.append(f"共 {total} 条结果（显示 {offset+1}-{offset+len(results)}）：")
    lines.append("-" * 80)

    for i, r in enumerate(results):
        cities = r.get("cities", [])
        city_str = f"[{'|'.join(cities)}]" if cities else ""
        source = r.get("source_name", r.get("source", ""))
        stars = "★" * r.get("importance", 0)
        lines.append(
            f"\n{i+1}. {stars} {city_str} [{source}] {r['title']}"
        )
        if r.get("ai_summary"):
            lines.append(f"   {r['ai_summary'][:120]}")
        lines.append(f"   日期: {r['date']} | 领域: {', '.join(r.get('domain', []))} | 标签: {', '.join(r.get('tags', []))}")

    lines.append("\n" + "-" * 80)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="新闻搜索工具")
    parser.add_argument("-k", "--keyword", help="关键词搜索")
    parser.add_argument("-d", "--domain", help="领域筛选: 科技/AI, 经济/金融, 政治/国际关系, 社会/民生")
    parser.add_argument("-c", "--city", help="城市筛选: 北京, 上海, 深圳, 苏州, 南京, 淮安")
    parser.add_argument("-s", "--source", help="来源筛选: cls-hot, thepaper, toutiao, weibo 等")
    parser.add_argument("-i", "--importance", type=int, default=0, help="最低重要性 (1-5)")
    parser.add_argument("--from", dest="date_from", help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("-n", "--limit", type=int, default=20, help="返回条数")
    parser.add_argument("--offset", type=int, default=0, help="偏移量")
    parser.add_argument("--count", action="store_true", help="仅显示计数")
    args = parser.parse_args()

    init_db()

    if args.count:
        total = count_news(
            date_from=args.date_from, date_to=args.date_to,
            domain=args.domain, city=args.city, source=args.source,
        )
        print(f"符合条件的新闻总数: {total}")
        return

    results = search_news(
        keyword=args.keyword, domain=args.domain, city=args.city,
        source=args.source, min_importance=args.importance,
        date_from=args.date_from, date_to=args.date_to,
        limit=args.limit, offset=args.offset,
    )
    total = count_news(
        date_from=args.date_from, date_to=args.date_to,
        domain=args.domain, city=args.city, source=args.source,
    )

    print(format_results(results, total, args.offset))


if __name__ == "__main__":
    main()
