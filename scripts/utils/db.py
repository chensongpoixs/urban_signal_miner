"""
数据库操作封装 — 支持 SQLite / MySQL 双后端，通过 config/settings.yaml 切换。

接口统一：调用方无需关心底层是 SQLite 还是 MySQL。
"""

from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── 配置加载 ─────────────────────────────────────────────

def _load_db_config() -> dict:
    import yaml
    settings_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
    with open(settings_path) as f:
        data = yaml.safe_load(f)
    return data.get("database", {})


def _mask_url(url: str) -> str:
    """隐藏密码后返回可安全打印的 URL。"""
    import re
    return re.sub(r"://.*?@", "://***:***@", url)


# ── 连接工厂 ─────────────────────────────────────────────

class _DB:
    """统一数据库连接包装。"""

    def __init__(self):
        cfg = _load_db_config()
        self._type = cfg.get("type", "sqlite")

        if self._type == "mysql":
            self._init_mysql(cfg["mysql"])
        else:
            self._init_sqlite(cfg.get("sqlite", {}))

    # ── SQLite ──

    def _init_sqlite(self, cfg: dict):
        import sqlite3
        db_path = Path(__file__).parent.parent.parent / cfg.get("path", "db/news.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._placeholder = "?"
        self._auto_inc = "INTEGER PRIMARY KEY AUTOINCREMENT"
        self._text_type = "TEXT"
        self._json_type = "TEXT"
        self._bool_type = "INTEGER"
        logger.info("SQLite connected: %s", db_path)

    # ── MySQL ──

    def _init_mysql(self, cfg: dict):
        try:
            import pymysql
        except ImportError:
            logger.error("pymysql not found. Install: pip install pymysql")
            sys.exit(1)

        host = cfg.get("host", "127.0.0.1")
        port = cfg.get("port", 3306)
        user = cfg.get("user", "root")
        password = cfg.get("password") or os.environ.get("MYSQL_PASSWORD", "")
        database = cfg.get("database", "daily_news")
        charset = cfg.get("charset", "utf8mb4")

        # 先创建数据库（如果不存在）
        tmp_conn = pymysql.connect(
            host=host, port=port, user=user, password=password, charset=charset,
        )
        with tmp_conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                f"CHARACTER SET {charset} COLLATE {charset}_unicode_ci"
            )
        tmp_conn.close()

        self._mysql_config = (host, port, user, password, database, charset)
        self._conn = pymysql.connect(
            host=host, port=port, user=user, password=password,
            database=database, charset=charset,
            autocommit=True, connect_timeout=10, read_timeout=30,
        )
        self._placeholder = "%s"
        self._auto_inc = "INT AUTO_INCREMENT PRIMARY KEY"
        self._text_type = "TEXT"
        self._json_type = "JSON"
        self._bool_type = "TINYINT(1)"
        logger.info("MySQL connected: %s", _mask_url(f"mysql://{user}@***@{host}:{port}/{database}"))

    # ── 通用接口 ──

    @property
    def type(self) -> str:
        return self._type

    def _ping(self):
        """Check connection health, reconnect if needed (MySQL only)."""
        if self._type != "mysql":
            return
        try:
            self._conn.ping(reconnect=True)
        except Exception as e:
            logger.warning("MySQL connection lost, reconnecting: %s", e)
            import pymysql
            host, port, user, password, database, charset = self._mysql_config
            self._conn = pymysql.connect(
                host=host, port=port, user=user, password=password,
                database=database, charset=charset,
                autocommit=True, connect_timeout=10, read_timeout=30,
            )

    def execute(self, sql: str, params=None):
        """执行 SQL，自动转换占位符。MySQL 连接断开时自动重连。"""
        self._ping()
        if params is None:
            params = []
        sql = sql.replace("?", self._placeholder)
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def executescript(self, sql: str):
        """执行多条 SQL 语句（仅 SQLite 用，MySQL 分号拆分）。"""
        if self._type == "sqlite":
            self._conn.executescript(sql)
        else:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    self.execute(stmt)
        self.commit()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def table_exists(self, table: str) -> bool:
        if self._type == "sqlite":
            row = self.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
        else:
            row = self.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s",
                (table,),
            ).fetchone()
        return row is not None


# ── 全局实例 ─────────────────────────────────────────────

_db: Optional[_DB] = None


def get_db() -> _DB:
    global _db
    if _db is None:
        _db = _DB()
    return _db


# ── 公共 API（与旧版兼容）────────────────────────────────

def init_db():
    """初始化所有表结构。幂等操作。"""
    db = get_db()

    if db.type == "sqlite":
        db.executescript("""
            CREATE TABLE IF NOT EXISTS news_index (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                source TEXT NOT NULL,
                source_name TEXT,
                source_url TEXT,
                rank INTEGER,
                title TEXT NOT NULL,
                domain TEXT DEFAULT '[]',
                cities TEXT DEFAULT '[]',
                entities TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                importance INTEGER DEFAULT 0,
                ai_summary TEXT DEFAULT '',
                ai_why_matters TEXT DEFAULT '',
                file_path TEXT NOT NULL,
                word_count INTEGER DEFAULT 0,
                processed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_news_date ON news_index(date);
            CREATE INDEX IF NOT EXISTS idx_news_source ON news_index(source);
            CREATE INDEX IF NOT EXISTS idx_news_importance ON news_index(importance);

            CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5(
                title, ai_summary, tags, tokenize='unicode61'
            );

            CREATE TABLE IF NOT EXISTS processed_files (
                file_path TEXT PRIMARY KEY,
                processed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS reports_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_type TEXT NOT NULL,
                period_key TEXT NOT NULL,
                file_path TEXT NOT NULL,
                news_count INTEGER,
                key_findings TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
    else:
        # MySQL --- DROP TABLE IF EXISTS news_index; CREATE TABLE news_index (...)
        db.executescript("""
             CREATE TABLE  IF NOT EXISTS news_index (
            
                id VARCHAR(64) PRIMARY KEY,
                date DATE NOT NULL,
                source VARCHAR(32) NOT NULL,
                source_name VARCHAR(64),
                source_url VARCHAR(512),
                rank INT,
                title VARCHAR(512) NOT NULL,
                domain JSON,
                cities JSON,
                entities JSON,
                tags JSON,
                importance TINYINT DEFAULT 0,
                ai_summary TEXT,
                ai_why_matters TEXT,
                file_path VARCHAR(256) NOT NULL,
                word_count INT DEFAULT 0,
                processed_at DATETIME,
                INDEX idx_news_date (date),
                INDEX idx_news_source (source),
                INDEX idx_news_importance (importance),
                FULLTEXT INDEX news_fts (title, ai_summary)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            DROP TABLE IF EXISTS processed_files;
            CREATE TABLE processed_files (
                file_path VARCHAR(512) PRIMARY KEY,
                processed_at DATETIME
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS reports_index (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_type VARCHAR(32) NOT NULL,
                period_key VARCHAR(32) NOT NULL,
                file_path VARCHAR(256) NOT NULL,
                news_count INT,
                key_findings JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

    logger.info("Database tables initialized [%s]", db.type)


def insert_news(record: Dict[str, Any]):
    """插入或替换一条新闻索引记录。校验必填字段。"""
    # 数据校验
    import re
    news_id = record.get("id", "")
    title = record.get("title", "")
    date = record.get("date", "")
    importance = record.get("importance", 0)

    if not news_id:
        raise ValueError("insert_news: id is required")
    if not title:
        raise ValueError("insert_news: title is required")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date)):
        raise ValueError(f"insert_news: invalid date format '{date}', expected YYYY-MM-DD")
    if not (1 <= importance <= 5):
        raise ValueError(f"insert_news: importance out of range {importance}, expected 1-5")

    db = get_db()
    sql = f"""
        REPLACE INTO news_index
            (id, date, source, source_name, source_url, rank, title,
             domain, cities, entities, tags, importance,
             ai_summary, ai_why_matters, file_path, word_count, processed_at)
        VALUES ({",".join(["?"] * 17)})
    """
    from datetime import datetime

    db.execute(sql, (
        record.get("id"), record.get("date"), record.get("source"),
        record.get("source_name"), record.get("source_url"), record.get("rank"),
        record.get("title"),
        json.dumps(record.get("domain", []), ensure_ascii=False),
        json.dumps(record.get("cities", []), ensure_ascii=False),
        json.dumps(record.get("entities", []), ensure_ascii=False),
        json.dumps(record.get("tags", []), ensure_ascii=False),
        record.get("importance", 0),
        record.get("ai_summary", ""), record.get("ai_why_matters", ""),
        record.get("file_path"), record.get("word_count", 0),
        datetime.now().isoformat(),
    ))
    db.commit()


def search_news(
    keyword: Optional[str] = None,
    domain: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
    min_importance: int = 0,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """多维度组合查询。MySQL 走 FULLTEXT，SQLite 走 FTS5。"""
    db = get_db()

    if keyword and db.type == "sqlite":
        base = "SELECT ni.* FROM news_index ni JOIN news_fts nf ON ni.rowid = nf.rowid WHERE news_fts MATCH ?"
        params: List[Any] = [keyword]
    elif keyword and db.type == "mysql":
        base = "SELECT * FROM news_index WHERE MATCH(title, ai_summary) AGAINST(%s IN BOOLEAN MODE)"
        params = [keyword]
    else:
        base = "SELECT * FROM news_index WHERE 1=1"
        params = []

    if domain:
        base += " AND domain LIKE ?"
        params.append(f"%{domain}%")
    if city:
        base += " AND cities LIKE ?"
        params.append(f"%{city}%")
    if source:
        base += " AND source = ?"
        params.append(source)
    if min_importance > 0:
        base += " AND importance >= ?"
        params.append(min_importance)
    if date_from:
        base += " AND date >= ?"
        params.append(date_from)
    if date_to:
        base += " AND date <= ?"
        params.append(date_to)

    base += " ORDER BY date DESC, importance DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cur = db.execute(base, params)
    rows = cur.fetchall()

    results = []
    for r in rows:
        if db.type == "sqlite":
            d = dict(r)
        else:
            # pymysql returns dict-like cursor if we use DictCursor
            d = r if isinstance(r, dict) else dict(zip([c[0] for c in cur.description], r))
        for field in ("domain", "cities", "entities", "tags"):
            val = d.get(field, "[]")
            if isinstance(val, str):
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        results.append(d)
    return results


def count_news(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    domain: Optional[str] = None,
    city: Optional[str] = None,
    source: Optional[str] = None,
) -> int:
    db = get_db()
    sql = "SELECT COUNT(*) FROM news_index WHERE 1=1"
    params: List[Any] = []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    if domain:
        sql += " AND domain LIKE ?"
        params.append(f"%{domain}%")
    if city:
        sql += " AND cities LIKE ?"
        params.append(f"%{city}%")
    if source:
        sql += " AND source = ?"
        params.append(source)
    row = db.execute(sql, params).fetchone()
    return row[0] if row else 0


def get_top_news(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_importance: int = 3,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    return search_news(date_from=date_from, date_to=date_to,
                       min_importance=min_importance, limit=limit)


def get_source_stats(date_from: str, date_to: str) -> List[Dict]:
    db = get_db()
    cur = db.execute(
        "SELECT source, source_name, COUNT(*) as cnt, AVG(importance) as avg_imp "
        "FROM news_index WHERE date BETWEEN ? AND ? "
        "GROUP BY source ORDER BY cnt DESC",
        (date_from, date_to),
    )
    rows = cur.fetchall()
    if db.type == "sqlite":
        return [dict(r) for r in rows]
    else:
        return [dict(zip([c[0] for c in cur.description], r)) for r in rows]


def mark_file_processed(file_path: str):
    """标记文件已处理，静默处理数据库写入失败。"""
    try:
        db = get_db()
        from datetime import datetime
        db.execute(
            "REPLACE INTO processed_files VALUES (?, ?)",
            (file_path, datetime.now().isoformat()),
        )
        db.commit()
    except Exception as e:
        logger.warning("Mark file processed failed %s: %s", file_path, e)


def is_file_processed(file_path: str) -> bool:
    db = get_db()
    cur = db.execute("SELECT 1 FROM processed_files WHERE file_path = ?", (file_path,))
    return cur.fetchone() is not None


def get_unprocessed_files(all_paths: List[str]) -> List[str]:
    db = get_db()
    placeholders = ",".join(["?"] * len(all_paths)) if all_paths else "''"
    cur = db.execute(
        f"SELECT file_path FROM processed_files WHERE file_path IN ({placeholders})",
        all_paths,
    )
    processed = {r[0] if isinstance(r, (tuple, list)) else r["file_path"] for r in cur.fetchall()}
    return [p for p in all_paths if p not in processed]


def extract_key_findings(report_text: str, max_chars: int = 500) -> str:
    """Extract first substantive paragraph from report text for index."""
    # Skip header lines (starting with #) and blank lines
    lines = report_text.split("\n")
    body = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            if body:  # stop at first blank/header after body
                break
            continue
        body.append(stripped)
        if sum(len(l) for l in body) >= max_chars:
            break
    return " ".join(body)[:max_chars]


def insert_report(report_type: str, period_key: str, file_path: str, news_count: int = 0, key_findings: str = ""):
    """插入一条报告索引记录。"""
    db = get_db()
    from datetime import datetime
    sql = f"""
        INSERT INTO reports_index (report_type, period_key, file_path, news_count, key_findings, created_at)
        VALUES ({",".join(["?"] * 6)})
    """
    db.execute(sql, (report_type, period_key, file_path, news_count, key_findings, datetime.now().isoformat()))
    db.commit()
