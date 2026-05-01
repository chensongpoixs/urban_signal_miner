"""News sync service — triggers git pull from ModelScope repository."""
import subprocess
import threading
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
NEWS_DIR = PROJECT_ROOT / "news-corpus"

# Sync state
_sync_lock = threading.Lock()
_sync_running = False
_last_sync = {"status": "never", "message": "", "new_files": 0, "timestamp": None}


def get_sync_status() -> dict:
    """Return current sync state."""
    return {
        "running": _sync_running,
        "last_sync": _last_sync,
    }


def run_sync() -> dict:
    """Execute git pull and scan for new files. Thread-safe."""
    global _sync_running, _last_sync

    with _sync_lock:
        if _sync_running:
            return {"status": "skipped", "message": "Sync already in progress", "new_files": 0}
        _sync_running = True

    try:
        logger.info("=== News sync started ===")

        # ── Check if news-corpus exists ──
        if not NEWS_DIR.exists():
            msg = "news-corpus directory not found. Clone first: git clone https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus.git news-corpus"
            logger.error(msg)
            result = {"status": "error", "message": msg, "new_files": 0}
            _last_sync = {**result, "timestamp": datetime.now().isoformat()}
            return result

        # ── Git pull ──
        try:
            proc = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=str(NEWS_DIR),
                capture_output=True,
                text=True,
                timeout=120,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            logger.info("git pull stdout: %s", stdout)
            if stderr:
                logger.info("git pull stderr: %s", stderr)

            if proc.returncode != 0:
                msg = f"git pull failed (code={proc.returncode}): {stderr}"
                logger.error(msg)
                result = {"status": "error", "message": msg, "new_files": 0}
                _last_sync = {**result, "timestamp": datetime.now().isoformat()}
                return result

            already_updated = "Already up to date" in stdout
        except subprocess.TimeoutExpired:
            msg = "git pull timed out (120s)"
            logger.error(msg)
            result = {"status": "error", "message": msg, "new_files": 0}
            _last_sync = {**result, "timestamp": datetime.now().isoformat()}
            return result

        # ── Count unenhanced/new files ──
        try:
            import sys
            sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
            from utils.file_utils import get_unenhanced_files, get_date_range

            new_files = get_unenhanced_files(NEWS_DIR)
            new_count = len(new_files)
            earliest, latest = get_date_range(NEWS_DIR)
            logger.info("Found %d unenhanced files | date range: %s ~ %s", new_count, earliest, latest)

            if already_updated:
                msg = f"Already up to date. {new_count} unenhanced files pending. Data range: {earliest} ~ {latest}"
                result = {
                    "status": "ok",
                    "message": msg,
                    "new_files": new_count,
                    "date_from": str(earliest) if earliest else None,
                    "date_to": str(latest) if latest else None,
                    "already_updated": True,
                }
            else:
                msg = f"Updated successfully. {new_count} unenhanced files pending. Data range: {earliest} ~ {latest}"
                result = {
                    "status": "ok",
                    "message": msg,
                    "new_files": new_count,
                    "date_from": str(earliest) if earliest else None,
                    "date_to": str(latest) if latest else None,
                    "already_updated": False,
                }
        except Exception as e:
            logger.warning("File scan failed: %s", e)
            msg = f"git pull done, but file scan failed: {e}"
            result = {"status": "ok", "message": msg, "new_files": -1}

        _last_sync = {**result, "timestamp": datetime.now().isoformat()}
        logger.info("Sync completed: %s", result["status"])
        return result

    except Exception as e:
        logger.exception("Sync failed: %s", e)
        result = {"status": "error", "message": str(e), "new_files": 0}
        _last_sync = {**result, "timestamp": datetime.now().isoformat()}
        return result
    finally:
        with _sync_lock:
            _sync_running = False
