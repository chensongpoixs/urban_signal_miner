#!/usr/bin/env python3
"""索引同步 — 从 enhanced Markdown 文件中读取 YAML frontmatter 同步到数据库。"""
import sys
import yaml
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, insert_news, mark_file_processed
from utils.file_utils import get_corpus_files
from utils.logging_config import setup_logging

logger = setup_logging("index_sync", "index_sync.log")

NEWS_DIR = Path(__file__).parent.parent / "news-corpus"


def parse_frontmatter(filepath: Path) -> dict | None:
    """从 Markdown 文件读取 YAML frontmatter。"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return None

    if not content.strip().startswith("---"):
        return None

    # 提取 YAML 块
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
        data["file_path"] = str(filepath.relative_to(NEWS_DIR))
        return data
    except yaml.YAMLError as e:
        logger.warning("YAML parse failed %s: %s", filepath.name, e)
        return None


def sync_all(incremental: bool = False):
    """Sync all enhanced .md files to database.

    Args:
        incremental: If True, only sync files not yet in processed_files.
                     If False (default), full sync with REPLACE INTO.
    """
    from utils.db import is_file_processed, get_db
    init_db()
    files = get_corpus_files(NEWS_DIR)

    if incremental:
        unprocessed = []
        for fp in files:
            rel = str(fp.relative_to(NEWS_DIR))
            if not is_file_processed(rel):
                unprocessed.append(fp)
        skipped = len(files) - len(unprocessed)
        logger.info("Incremental sync: %d total, %d skipped, %d pending", len(files), skipped, len(unprocessed))
        files = unprocessed

    total = len(files)
    if not incremental:
        logger.info("Full sync: %d files", total)

    synced = 0
    for fp in files:
        data = parse_frontmatter(fp)
        if data is None:
            continue
        try:
            insert_news(data)
            rel = str(fp.relative_to(NEWS_DIR))
            mark_file_processed(rel)
            synced += 1
        except Exception as e:
            logger.error("Sync failed %s: %s", fp.name, e)

    logger.info("Sync complete: %d/%d", synced, total)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sync enhanced Markdown to database")
    parser.add_argument("--incremental", action="store_true", help="Only sync unprocessed files")
    args = parser.parse_args()
    sync_all(incremental=args.incremental)
