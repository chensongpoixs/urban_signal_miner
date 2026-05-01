"""统一日志配置 — RotatingFileHandler + 控制台输出。"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).parent.parent.parent / "logs"


def setup_logging(name: str, logfile: str, level: int = logging.INFO) -> logging.Logger:
    """配置日志：控制台 + 文件轮转（10MB×5个备份）。

    Args:
        name: logger 名称
        logfile: 日志文件名（如 "classify.log"）
        level: 日志级别

    Returns:
        配置好的 logger
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    # 文件轮转
    file_handler = RotatingFileHandler(
        LOG_DIR / logfile,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # ── Always ensure api.llm logger has handlers for LLM request/response logging ──
    llm_logger = logging.getLogger("api.llm")
    if not llm_logger.handlers:
        llm_logger.setLevel(logging.DEBUG)
        llm_logger.addHandler(console)
        llm_file = logging.FileHandler(
            LOG_DIR / "llm_calls.log", encoding="utf-8"
        )
        llm_file.setFormatter(formatter)
        llm_logger.addHandler(llm_file)

    return logger
