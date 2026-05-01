"""Dashboard data aggregation service."""
from datetime import datetime, timedelta
from utils import db as db_module


class DashboardService:

    def get_stats(self, days: int = 30):
        today = datetime.now()
        start = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        yesterday_start = (today - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        yesterday_end = (today - timedelta(days=days + 1)).strftime("%Y-%m-%d")

        # Stats for current period
        current = db_module.get_news_total_stats(start, end)
        # Stats for previous period (for change calculation)
        prev = db_module.get_news_total_stats(yesterday_start, yesterday_end)

        def calc_change(cur: float, prev: float) -> str:
            if prev == 0:
                return "+100%" if cur > 0 else "0%"
            pct = (cur - prev) / prev * 100
            return f"{'+' if pct > 0 else ''}{pct:.0f}%"

        news_by_day = db_module.get_daily_news_counts(start, end)
        top_domains = db_module.get_domain_distribution(start, end)
        top_cities = db_module.get_city_distribution(start, end)
        top_sources = db_module.get_news_count_by_source(start, end)
        imp_dist = db_module.get_importance_distribution(start, end)
        recent_reports = db_module.get_reports(limit=5)

        # Today stats
        today_str = today.strftime("%Y-%m-%d")
        today_stats = db_module.get_news_total_stats(today_str, today_str)

        # This week stats
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        week_stats = db_module.get_news_total_stats(
            monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")
        )

        return {
            "stats": [
                {
                    "label": "新闻总数",
                    "value": f"{current['total']:,}",
                    "change": calc_change(current["total"], prev["total"]),
                },
                {
                    "label": "今日新闻",
                    "value": str(today_stats["total"]),
                    "change": "",
                },
                {
                    "label": "本周新闻",
                    "value": str(week_stats["total"]),
                    "change": "",
                },
                {
                    "label": "平均重要性",
                    "value": f"{current['avg_importance']:.1f}",
                    "change": "",
                },
            ],
            "news_by_day": [
                {
                    "date": str(d.get("date", "")),
                    "count": d.get("cnt", 0),
                    "avg_importance": round(float(d.get("avg_imp", 0)), 2),
                }
                for d in news_by_day
            ],
            "top_domains": [
                {"domain": d["domain"], "count": d["count"], "percentage": d["percentage"]}
                for d in top_domains[:6]
            ],
            "top_cities": [
                {"city": c["city"], "count": c["count"], "percentage": c["percentage"]}
                for c in top_cities[:6]
            ],
            "top_sources": [
                {
                    "source": s.get("source", ""),
                    "source_name": s.get("source_name", ""),
                    "count": s.get("cnt", 0),
                    "avg_importance": round(float(s.get("avg_imp", 0)), 2) if s.get("avg_imp") else None,
                }
                for s in top_sources[:10]
            ],
            "importance_distribution": {str(k): v for k, v in sorted(imp_dist.items())},
            "recent_reports": [
                {
                    "id": r.get("id", 0),
                    "report_type": r.get("report_type", ""),
                    "period_key": r.get("period_key", ""),
                    "news_count": r.get("news_count", 0),
                    "key_findings": (r.get("key_findings", "") or "")[:200],
                    "created_at": str(r.get("created_at", "")),
                }
                for r in recent_reports
            ],
        }
