#!/usr/bin/env python3
"""同步新闻数据 — git pull ModelScope 仓库，检测新增文件。"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.file_utils import get_unenhanced_files, get_date_range
from utils.logging_config import setup_logging

logger = setup_logging("sync", "sync.log")

PROJECT_DIR = Path(__file__).parent.parent
NEWS_DIR = PROJECT_DIR / "news-corpus"


def git_pull() -> bool:
    """执行 git pull，返回是否有更新。"""
    if not NEWS_DIR.exists():
        logger.warning("news-corpus dir not found. Clone first: git clone https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus.git news-corpus")
        return False

    logger.info("Starting git pull: %s", NEWS_DIR)
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=str(NEWS_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        logger.info("git pull stdout: %s", result.stdout.strip())
        if result.stderr:
            logger.info("git pull stderr: %s", result.stderr.strip())
        if "Already up to date" in result.stdout:
            logger.info("Already up to date")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("git pull timed out")
        return False
    except Exception as e:
        logger.error("git pull failed: %s", e)
        return False


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("News sync started")

    success = git_pull()

    if not NEWS_DIR.exists():
        logger.error("Cannot scan: news-corpus dir not found. Clone ModelScope repo first")
        logger.error("  git clone https://www.modelscope.cn/datasets/chensongpoixs/daily_news_corpus.git news-corpus")
        sys.exit(1)

    if not success:
        logger.error("git pull failed, latest data may not be available")

    new_files = get_unenhanced_files(NEWS_DIR)
    logger.info("Found %d unenhanced files", len(new_files))
    if new_files:
        print("\n".join(str(f) for f in new_files))
    earliest, latest = get_date_range(NEWS_DIR)
    logger.info("Data date range: %s ~ %s", earliest, latest)

    logger.info("News sync complete")
    sys.exit(0 if success else 1)
