#!/usr/bin/env python3
"""同步新闻数据 — git pull ModelScope 仓库，检测新增文件。"""
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "sync.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent
NEWS_DIR = PROJECT_DIR / "news-corpus"


def git_pull() -> bool:
    """执行 git pull，返回是否有更新。"""
    logger.info("开始 git pull: %s", NEWS_DIR)
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
            logger.info("仓库已是最新")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("git pull 超时")
        return False
    except Exception as e:
        logger.error("git pull 失败: %s", e)
        return False


def find_new_md_files() -> list[Path]:
    """查找所有未被增强（无 YAML frontmatter）的 .md 文件。"""
    new_files = []
    for date_dir in sorted(NEWS_DIR.iterdir()):
        if not date_dir.is_dir() or not date_dir.name.isdigit():
            continue
        for source_dir in sorted(date_dir.iterdir()):
            if not source_dir.is_dir():
                continue
            for md_file in sorted(source_dir.glob("*.md")):
                if _needs_enhancement(md_file):
                    new_files.append(md_file)
    return new_files


def _needs_enhancement(filepath: Path) -> bool:
    """检查 .md 文件是否缺少 YAML frontmatter（即未被 AI 增强过）。"""
    try:
        content = filepath.read_text(encoding="utf-8")
        # YAML frontmatter 以 --- 开头
        return not content.strip().startswith("---")
    except Exception:
        return False


def get_date_range() -> tuple[str, str]:
    """获取 news-corpus 中最早和最晚的日期目录。"""
    date_dirs = sorted(
        [d for d in NEWS_DIR.iterdir() if d.is_dir() and d.name.isdigit()]
    )
    if not date_dirs:
        return datetime.now().strftime("%Y%m%d"), datetime.now().strftime("%Y%m%d")
    earliest = date_dirs[0].name
    latest = date_dirs[-1].name
    return earliest, latest


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("新闻同步开始")
    git_pull()

    new_files = find_new_md_files()
    logger.info("发现 %d 个未增强的文件", len(new_files))

    if new_files:
        # 输出文件列表供 classify.py 使用
        print("\n".join(str(f) for f in new_files))

    earliest, latest = get_date_range()
    logger.info("数据日期范围: %s ~ %s", earliest, latest)
    logger.info("新闻同步完成")
