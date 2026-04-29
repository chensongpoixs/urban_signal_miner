#!/usr/bin/env python3
"""CLI news search tool — supports table, JSON, and CSV output."""
import sys
import csv
import json
import argparse
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, search_news, count_news


def format_table(results, total: int, offset: int = 0) -> str:
    """Format results as a human-readable table."""
    lines = []
    lines.append(f"Total {total} results (showing {offset+1}-{offset+len(results)}):")
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
        lines.append(f"   Date: {r['date']} | Domain: {', '.join(r.get('domain', []))} | Tags: {', '.join(r.get('tags', []))}")

    lines.append("\n" + "-" * 80)
    return "\n".join(lines)


def results_to_dicts(results) -> list[dict]:
    """Convert results to a list of flat dicts suitable for JSON/CSV output."""
    flat = []
    for r in results:
        d = {
            "id": r.get("id", ""),
            "date": r.get("date", ""),
            "source": r.get("source", ""),
            "source_name": r.get("source_name", ""),
            "rank": r.get("rank", ""),
            "title": r.get("title", ""),
            "domain": ", ".join(r.get("domain", [])),
            "cities": ", ".join(r.get("cities", [])),
            "tags": ", ".join(r.get("tags", [])),
            "importance": r.get("importance", 0),
            "ai_summary": r.get("ai_summary", ""),
            "ai_why_matters": r.get("ai_why_matters", ""),
            "file_path": r.get("file_path", ""),
        }
        flat.append(d)
    return flat


def main():
    parser = argparse.ArgumentParser(description="News search tool")
    parser.add_argument("-k", "--keyword", help="Keyword search")
    parser.add_argument("-d", "--domain", help="Domain filter (e.g. 科技/AI, 经济/金融)")
    parser.add_argument("-c", "--city", help="City filter (e.g. 北京, 上海, 深圳)")
    parser.add_argument("-s", "--source", help="Source filter: cls-hot, thepaper, toutiao, etc.")
    parser.add_argument("-i", "--importance", type=int, default=0, help="Min importance (1-5)")
    parser.add_argument("--from", dest="date_from", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", help="End date (YYYY-MM-DD)")
    parser.add_argument("-n", "--limit", type=int, default=20, help="Max results")
    parser.add_argument("--offset", type=int, default=0, help="Offset")
    parser.add_argument("--count", action="store_true", help="Only show count")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table",
                        help="Output format (default: table)")
    parser.add_argument("--output", "-o", help="Output to file (stdout if omitted)")
    args = parser.parse_args()

    try:
        init_db()

        if args.count:
            total = count_news(
                date_from=args.date_from, date_to=args.date_to,
                domain=args.domain, city=args.city, source=args.source,
            )
            print(f"Total matching news: {total}")
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

        # Format output
        if args.format == "json":
            output = json.dumps(results_to_dicts(results), ensure_ascii=False, indent=2)
        elif args.format == "csv":
            buf = StringIO()
            dicts = results_to_dicts(results)
            if dicts:
                writer = csv.DictWriter(buf, fieldnames=dicts[0].keys())
                writer.writeheader()
                writer.writerows(dicts)
            output = buf.getvalue()
        else:
            output = format_table(results, total, args.offset)

        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
            print(f"Results saved to: {args.output}")
        else:
            print(output)

    except Exception as e:
        print(f"Search failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
