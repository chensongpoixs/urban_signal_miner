"""FastAPI dependencies."""
from utils.db import get_db as _get_db, init_db


def get_db():
    """Dependency: get DB singleton (lazy-init on first call)."""
    return _get_db()
