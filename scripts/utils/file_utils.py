"""通用工具函数。"""
import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def get_corpus_files(corpus_dir: Path) -> List[Path]:
    """扫描 news-corpus 目录下所有原始 .md 文件（不含 enhanced 文件）。

    Args:
        corpus_dir: news-corpus 目录路径

    Returns:
        按日期/来源排序的 .md 文件路径列表
    """
    if not corpus_dir.exists():
        raise FileNotFoundError(f"News corpus dir not found: {corpus_dir}")

    files = []
    for date_dir in sorted(corpus_dir.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.isdigit():
            continue
        for source_dir in sorted(date_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for md_file in sorted(source_dir.glob("*.md")):
                if not md_file.name.startswith("."):
                    files.append(md_file)
    return files


def get_unenhanced_files(corpus_dir: Path) -> List[Path]:
    """获取所有未被 AI 增强（无 YAML frontmatter）的 .md 文件。"""
    all_files = get_corpus_files(corpus_dir)
    unenhanced = []
    for fp in all_files:
        try:
            content = fp.read_text(encoding="utf-8")
            if not content.strip().startswith("---"):
                unenhanced.append(fp)
        except Exception:
            continue
    return unenhanced


def get_date_range(corpus_dir: Path) -> tuple:
    """获取语料库中最早和最晚的日期目录。"""
    from datetime import datetime
    date_dirs = sorted(
        [d for d in corpus_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    )
    if not date_dirs:
        today = datetime.now().strftime("%Y%m%d")
        return today, today
    return date_dirs[0].name, date_dirs[-1].name
