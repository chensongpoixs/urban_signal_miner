"""One-click pipeline service — sync → classify → index → report.
Runs all steps in-process (NOT via subprocess) so that LLM request/response
logging is properly captured by the api.llm logger.
"""
import threading
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
NEWS_DIR = PROJECT_ROOT / "news-corpus"

_pipeline_lock = threading.Lock()
_pipeline_running = False
_pipeline_state = {
    "status": "idle",       # idle | running | completed | failed
    "step": "",             # current step name
    "step_index": 0,
    "total_steps": 0,
    "steps": [],            # list of {name, status: pending|running|ok|failed}
    "message": "",
    "started_at": None,
    "finished_at": None,
}


def get_pipeline_status() -> dict:
    return {
        "running": _pipeline_running,
        "state": dict(_pipeline_state),
    }


def _step_ok(name: str) -> bool:
    """Run a step-by-name and return True if it succeeded."""
    logger.info("Pipeline step starting: %s", name)

    if name == "配置校验":
        from config_validate import check_settings
        errors = check_settings()
        if errors:
            logger.error("Config validation failed: %s", errors)
            return False
        return True

    elif name == "数据同步":
        from sync_news import git_pull
        ok = git_pull()
        if not ok:
            logger.warning("git pull failed or already up to date")
        # Also scan files to return useful info
        from file_utils import get_unenhanced_files, get_date_range
        if NEWS_DIR.exists():
            new_files = get_unenhanced_files(NEWS_DIR)
            logger.info("Unenhanced files found: %d", len(new_files))
            earliest, latest = get_date_range(NEWS_DIR)
            logger.info("Data date range: %s ~ %s", earliest, latest)
        return True  # Not a fatal error if git pull fails

    elif name == "AI 打标":
        from classify import process_files
        from file_utils import get_unenhanced_files
        from config_loader import get_settings

        settings = get_settings()
        workers = settings.get("llm_limits", {}).get("classify_workers", 1)

        filepaths = get_unenhanced_files(NEWS_DIR)
        logger.info("AI classify: %d files, workers=%d", len(filepaths), workers)

        # classify_limit is set as attribute by run_pipeline()
        limit = getattr(_step_ok, "_classify_limit", 0)
        if limit > 0:
            filepaths = filepaths[:limit]
            logger.info("AI classify limited to %d files", limit)

        if not filepaths:
            logger.info("No unenhanced files to classify")
            return True

        process_files(filepaths, dry_run=False, workers=workers)
        return True

    elif name == "索引同步":
        from index_sync import sync_all
        sync_all(incremental=False)
        return True

    elif name == "生成周报":
        from gen_weekly import generate_weekly
        path = generate_weekly(week_str=None)  # current week
        logger.info("Weekly report generated: %s", path)
        return True

    elif name == "生成月报":
        from gen_monthly import generate_monthly
        path = generate_monthly(month_str=None)  # current month
        logger.info("Monthly report generated: %s", path)
        return True

    else:
        logger.error("Unknown pipeline step: %s", name)
        return False


def run_pipeline(classify_limit: int = 0, skip_classify: bool = False) -> dict:
    """Run the full pipeline. Thread-safe. All steps run in-process."""
    global _pipeline_running, _pipeline_state

    with _pipeline_lock:
        if _pipeline_running:
            return {"status": "skipped", "message": "流水线正在运行中"}
        _pipeline_running = True

    steps = [
        {"name": "配置校验"},
        {"name": "数据同步"},
    ]
    if not skip_classify:
        steps.append({"name": "AI 打标"})
    steps += [
        {"name": "索引同步"},
        {"name": "生成周报"},
        {"name": "生成月报"},
    ]

    # Store classify_limit for _step_ok to pick up
    _step_ok._classify_limit = classify_limit

    _pipeline_state = {
        "status": "running",
        "step": "启动中...",
        "step_index": 0,
        "total_steps": len(steps),
        "steps": [{"name": s["name"], "status": "pending"} for s in steps],
        "message": "流水线启动",
        "started_at": datetime.now().isoformat(),
        "finished_at": None,
    }

    try:
        for i, step in enumerate(steps):
            _pipeline_state["step_index"] = i + 1
            _pipeline_state["step"] = step["name"]
            _pipeline_state["steps"][i]["status"] = "running"
            _pipeline_state["message"] = f"执行中: {step['name']} ({i+1}/{len(steps)})"
            logger.info("Pipeline [%d/%d] %s", i + 1, len(steps), step["name"])

            try:
                ok = _step_ok(step["name"])
                if ok:
                    _pipeline_state["steps"][i]["status"] = "ok"
                else:
                    _pipeline_state["steps"][i]["status"] = "failed"
                    logger.warning("Pipeline step [%s] failed but continuing", step["name"])
            except Exception as e:
                logger.exception("Pipeline step [%s] exception: %s", step["name"], e)
                _pipeline_state["steps"][i]["status"] = "failed"

        failed = [s for s in _pipeline_state["steps"] if s["status"] == "failed"]
        if failed:
            _pipeline_state["status"] = "completed"
            _pipeline_state["message"] = f"流水线完成（{len(failed)} 步失败：{', '.join(s['name'] for s in failed)}）"
        else:
            _pipeline_state["status"] = "completed"
            _pipeline_state["message"] = "流水线全部完成"
        _pipeline_state["step"] = "完成"
        _pipeline_state["finished_at"] = datetime.now().isoformat()
        logger.info("Pipeline completed")
        return {"status": "completed", "message": _pipeline_state["message"]}

    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        _pipeline_state["status"] = "failed"
        _pipeline_state["message"] = f"流水线异常: {e}"
        _pipeline_state["step"] = "异常终止"
        _pipeline_state["finished_at"] = datetime.now().isoformat()
        return {"status": "failed", "message": str(e)}

    finally:
        with _pipeline_lock:
            _pipeline_running = False
