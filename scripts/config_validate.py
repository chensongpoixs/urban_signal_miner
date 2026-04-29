#!/usr/bin/env python3
"""配置校验 — 启动前检查所有配置项是否有效。"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

OK = "✓"
FAIL = "✗"


def check_settings() -> list[str]:
    from utils.config_loader import _load_yaml
    errors = []
    try:
        cfg = _load_yaml("settings.yaml")
    except Exception as e:
        return [f"settings.yaml parse error: {e}"]

    # 数据库
    db = cfg.get("database", {})
    db_type = db.get("type", "sqlite")
    if db_type not in ("sqlite", "mysql"):
        errors.append(f"database.type invalid: {db_type}, supports sqlite/mysql only")
    if db_type == "sqlite":
        db_path = Path(__file__).parent.parent / db.get("sqlite", {}).get("path", "db/news.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {OK} SQLite path: {db_path}")
    elif db_type == "mysql":
        import pymysql
        mysql = db.get("mysql", {})
        try:
            conn = pymysql.connect(
                host=mysql.get("host", "127.0.0.1"),
                port=mysql.get("port", 3306),
                user=mysql.get("user", "root"),
                password=mysql.get("password") or os.environ.get("MYSQL_PASSWORD", ""),
                charset=mysql.get("charset", "utf8mb4"),
            )
            conn.close()
            print(f"  {OK} MySQL connected: {mysql.get('host')}:{mysql.get('port')}")
        except Exception as e:
            errors.append(f"MySQL connection failed: {e}")

    # 模型
    models = cfg.get("model", [])
    if not models:
        errors.append("model list is empty, at least one model required")
    else:
        for i, m in enumerate(models):
            if not m.get("model"):
                errors.append(f"model[{i}].model not configured")
            if not m.get("api_key") and not os.environ.get("ANTHROPIC_API_KEY"):
                errors.append(f"model[{i}].api_key not configured and ANTHROPIC_API_KEY env var not set")

    # 目录
    news_dir = Path(__file__).parent.parent / cfg.get("project", {}).get("news_dir", "news-corpus")
    if news_dir.exists():
        print(f"  {OK} News corpus dir: {news_dir}")
    else:
        errors.append(f"News corpus dir not found: {news_dir}, clone ModelScope repo first")

    # 报告目录
    reports_dir = Path(__file__).parent.parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    return errors


def main():
    print("Validating configuration...")
    errors = check_settings()

    if errors:
        print(f"\n{FAIL} Found {len(errors)} issue(s):")
        for e in errors:
            print(f"  - {e}")
        print("\nConfig validation failed. Fix issues and retry.")
        sys.exit(1)
    else:
        print(f"\n{OK} Config validation passed. System ready.")
        sys.exit(0)


if __name__ == "__main__":
    main()
