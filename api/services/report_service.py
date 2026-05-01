"""Report generation orchestration service.

Core logic: check DB → return existing → generate if missing → cache to DB + file.
Supports async generation with task_status polling.
"""
import sys
import uuid
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from utils import db as db_module
from api.services.markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"

# Single-threaded executor to avoid concurrent LLM API calls
_executor = ThreadPoolExecutor(max_workers=2)

parser = MarkdownParser()


class ReportService:

    def __init__(self):
        self._task_store: dict[str, dict] = {}
        self._task_lock = threading.Lock()

    # ── Retrieval ──

    def list_reports(
        self,
        report_type: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        offset = (page - 1) * page_size
        total = db_module.count_reports(report_type)
        items = db_module.get_reports(
            report_type=report_type,
            date_from=date_from,
            date_to=date_to,
            limit=page_size,
            offset=offset,
        )
        return {
            "items": [
                {
                    "id": r.get("id", 0),
                    "report_type": r.get("report_type", ""),
                    "period_key": r.get("period_key", ""),
                    "file_path": r.get("file_path", ""),
                    "news_count": r.get("news_count", 0),
                    "key_findings": (r.get("key_findings", "") or "")[:300],
                    "created_at": str(r.get("created_at", "")),
                }
                for r in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get_report(self, report_type: str, period_key: str) -> Optional[dict]:
        db_report = db_module.get_report_by_key(report_type, period_key)
        if not db_report:
            return None

        file_path = Path(db_report["file_path"])
        if not file_path.is_absolute():
            file_path = PROJECT_ROOT / file_path

        if not file_path.exists():
            return None

        markdown_text = file_path.read_text(encoding="utf-8")
        result = parser.parse(report_type, markdown_text)
        result["file_path"] = str(file_path.relative_to(PROJECT_ROOT))
        result["period_key"] = period_key
        return result

    # ── Generation ──

    def request_generate(self, request: Any) -> dict:
        """Create async generation task. Returns {task_id, status: 'pending'}."""
        # Normalize report type and period key
        report_type = request.report_type
        period_key = request.period_key

        if not period_key:
            period_key = self._default_period_key(report_type, request)

        # Check if already exists and not forcing regeneration
        if not request.force_regenerate:
            existing = self.get_report(report_type, period_key)
            if existing:
                return {
                    "task_id": "",
                    "status": "completed",
                    "message": "Report already exists",
                    "result": {
                        "report_type": report_type,
                        "period_key": period_key,
                        "exists": True,
                    },
                }

        task_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        task_data = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "Task queued",
            "result": None,
            "error": None,
            "created_at": now,
            "completed_at": None,
        }

        with self._task_lock:
            self._task_store[task_id] = task_data

        # Submit to thread pool
        _executor.submit(
            self._run_generation,
            task_id, report_type, period_key, request,
        )

        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Report generation queued",
            "result": None,
        }

    def get_task_status(self, task_id: str) -> Optional[dict]:
        with self._task_lock:
            return self._task_store.get(task_id)

    def _run_generation(self, task_id: str, report_type: str, period_key: str, request: Any):
        try:
            self._update_task(task_id, "running", 10, "Starting generation...")

            # Map report_type to generate function
            result_path = ""
            if report_type == "weekly":
                self._update_task(task_id, "running", 20, "Collecting weekly news...")
                result_path = self._generate_weekly(period_key)
            elif report_type == "monthly":
                self._update_task(task_id, "running", 20, "Collecting monthly news...")
                result_path = self._generate_monthly(period_key)
            elif report_type == "quarterly":
                self._update_task(task_id, "running", 15, "Phase 1: Domain summary...")
                result_path = self._generate_quarterly(request.offset)
            elif report_type == "special_city_compare":
                self._update_task(task_id, "running", 20, "Collecting city news...")
                result_path = self._generate_city_compare(request.months)
            elif report_type == "special_causal_chain":
                self._update_task(task_id, "running", 20, "Searching related news...")
                result_path = self._generate_causal_chain(request.topic, request.months)

            # Parse the generated report
            self._update_task(task_id, "running", 90, "Parsing report...")
            report_detail = self.get_report(report_type, period_key) or {}

            self._update_task(
                task_id, "completed", 100, "Generation complete",
                result={"report_type": report_type, "period_key": period_key, "file_path": str(result_path)},
            )
        except Exception as e:
            logger.exception("Report generation failed: %s", e)
            self._update_task(task_id, "failed", 0, "Generation failed", error=str(e))
        finally:
            import gc
            gc.collect()

    def _update_task(self, task_id: str, status: str, progress: int, message: str,
                     result: dict = None, error: str = None):
        with self._task_lock:
            if task_id in self._task_store:
                t = self._task_store[task_id]
                t["status"] = status
                t["progress"] = progress
                t["message"] = message
                if result:
                    t["result"] = result
                if error:
                    t["error"] = error
                if status in ("completed", "failed"):
                    t["completed_at"] = datetime.now().isoformat()

    # ── Delete ──

    def delete_report(self, report_type: str, period_key: str) -> bool:
        db_report = db_module.get_report_by_key(report_type, period_key)
        if db_report:
            file_path = Path(db_report["file_path"])
            if not file_path.is_absolute():
                file_path = PROJECT_ROOT / file_path
            if file_path.exists():
                file_path.unlink()
        return db_module.delete_report(report_type, period_key)

    # ── Internal: call existing generate functions ──

    def _generate_weekly(self, week_str: str) -> str:
        from gen_weekly import generate_weekly
        return generate_weekly(week_str=week_str)

    def _generate_monthly(self, month_str: str) -> str:
        from gen_monthly import generate_monthly
        return generate_monthly(month_str=month_str)

    def _generate_quarterly(self, offset: int) -> str:
        from gen_quarterly import generate_quarterly
        return generate_quarterly(offset=offset)

    def _generate_city_compare(self, months: int) -> str:
        from gen_city_compare import generate_city_compare
        return generate_city_compare(months=months)

    def _generate_causal_chain(self, topic: str, months: int) -> str:
        from gen_causal_chain import generate_causal_chain
        return generate_causal_chain(topic=topic, months=months)

    def _default_period_key(self, report_type: str, request: Any) -> str:
        """Generate default period_key if not provided."""
        now = datetime.now()
        if report_type == "weekly":
            monday = now - timedelta(days=now.weekday())
            return f"{monday.year}-W{monday.isocalendar()[1]:02d}"
        elif report_type == "monthly":
            return now.strftime("%Y-%m")
        elif report_type == "quarterly":
            q = (now.month - 1) // 3 + 1
            return f"{now.year}-Q{q}"
        elif report_type == "special_city_compare":
            return now.strftime("%Y-%m")
        elif report_type == "special_causal_chain":
            return request.topic or now.strftime("%Y-%m-%d")
        return ""

    # ── Available periods ──

    def get_available_periods(self, report_type: str) -> list[dict]:
        """Return list of periods that can be generated for this report type."""
        db = db_module.get_db()
        cur = db.execute("SELECT MIN(date), MAX(date) FROM news_index")
        row = cur.fetchone()
        if not row or not row[0]:
            return []

        if db.type == "sqlite":
            min_date_str = str(row["MIN(date)"])
            max_date_str = str(row["MAX(date)"])
        else:
            min_date_str = str(row[0]) if row[0] else ""
            max_date_str = str(row[1]) if row[1] else ""

        if not min_date_str:
            return []

        min_dt = datetime.strptime(min_date_str[:10], "%Y-%m-%d")
        max_dt = datetime.strptime(max_date_str[:10], "%Y-%m-%d")

        periods = []
        if report_type == "weekly":
            # Generate ISO weeks between min and max
            dt = min_dt
            while dt <= max_dt:
                week_key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
                mon = dt - timedelta(days=dt.weekday())
                sun = mon + timedelta(days=6)
                exists = db_module.check_report_exists("weekly", week_key)
                periods.append({
                    "period_key": week_key,
                    "label": f"Week {week_key[-2:]} ({mon.strftime('%m/%d')}~{sun.strftime('%m/%d')})",
                    "has_report": exists,
                })
                dt += timedelta(days=7)
        elif report_type == "monthly":
            dt = min_dt.replace(day=1)
            while dt <= max_dt:
                month_key = dt.strftime("%Y-%m")
                exists = db_module.check_report_exists("monthly", month_key)
                periods.append({
                    "period_key": month_key,
                    "label": dt.strftime("%Y-%m"),
                    "has_report": exists,
                })
                # Next month
                if dt.month == 12:
                    dt = dt.replace(year=dt.year + 1, month=1)
                else:
                    dt = dt.replace(month=dt.month + 1)
        elif report_type == "quarterly":
            q = (min_dt.month - 1) // 3 + 1
            dt = min_dt.replace(month=(q - 1) * 3 + 1, day=1)
            while dt <= max_dt:
                q = (dt.month - 1) // 3 + 1
                quarter_key = f"{dt.year}-Q{q}"
                exists = db_module.check_report_exists("quarterly", quarter_key)
                periods.append({
                    "period_key": quarter_key,
                    "label": quarter_key,
                    "has_report": exists,
                })
                dt = dt.replace(month=((dt.month - 1) // 3 + 1) * 3 + 1)
                if dt.month > 12:
                    dt = dt.replace(year=dt.year + 1, month=1)

        # Sort descending (newest first)
        periods.sort(key=lambda p: p["period_key"], reverse=True)
        return periods


# Singleton
report_service = ReportService()
