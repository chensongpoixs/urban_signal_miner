#!/usr/bin/env python3
"""索引同步 — 从 enhanced Markdown 文件中读取 YAML frontmatter 同步到数据库。"""
import sys
import yaml
import re
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from utils.db import init_db, insert_news, mark_file_processed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "sync.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

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
        logger.warning("YAML 解析失败 %s: %s", filepath.name, e)
        return None


def sync_all():
    """全量同步所有已增强的 .md 文件到数据库。"""
    init_db()

    files = []
    for date_dir in sorted(NEWS_DIR.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.isdigit():
            continue
        for source_dir in sorted(date_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for md_file in sorted(source_dir.glob("*.md")):
                if md_file.name.startswith("."):
                    continue
                files.append(md_file)

    total = len(files)
    logger.info("全量同步: %d 个文件", total)

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
            logger.error("同步失败 %s: %s", fp.name, e)

    logger.info("同步完成: %d/%d", synced, total)


if __name__ == "__main__":
    sync_all()
