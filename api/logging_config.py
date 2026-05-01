"""Centralized logging configuration for the API server."""
import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FORMAT = (
    "[%(asctime)s] %(levelname)-7s %(name)s | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Create root logger for the api package
api_logger = logging.getLogger("api")
api_logger.setLevel(logging.DEBUG)

# Create logger for LLM calls
llm_logger = logging.getLogger("api.llm")
llm_logger.setLevel(logging.DEBUG)


def setup_logging():
    """Configure logging handlers: console + rotating file."""

    # Prevent adding duplicate handlers on reload
    if api_logger.handlers:
        return

    # ── Console handler (DEBUG level) ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    api_logger.addHandler(console)

    # ── File handler (all logs) ──
    file_handler = logging.FileHandler(
        LOG_DIR / "api.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    api_logger.addHandler(file_handler)

    # ── LLM dedicated file (full request/response details) ──
    llm_file = logging.FileHandler(
        LOG_DIR / "llm_calls.log", encoding="utf-8"
    )
    llm_file.setLevel(logging.DEBUG)
    llm_file.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    llm_logger.addHandler(llm_file)

    # Also attach scripts.utils logger
    scripts_logger = logging.getLogger("scripts")
    scripts_logger.setLevel(logging.DEBUG)
    scripts_logger.addHandler(console)
    scripts_logger.addHandler(file_handler)

    api_logger.info("Logging system initialized | log_dir=%s", LOG_DIR)
