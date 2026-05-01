"""News search router."""
import re
import logging
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from utils import db as db_module
from api.models.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["news"])

# ── Project root for resolving relative news file paths ──
PROJECT_ROOT = Path(__file__).parent.parent.parent
NEWS_CORPUS = PROJECT_ROOT / "news-corpus"


def _extract_article_body(file_path: str) -> str:
    """Read markdown file and extract article body after '## 正文内容'."""
    # Normalize path separators (Windows backslash → forward slash)
    normalized = file_path.replace("\\", "/")
    full_path = NEWS_CORPUS / normalized

    if not full_path.exists():
        logger.warning("News file not found: %s", full_path)
        return ""

    try:
        content = full_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Cannot read news file %s: %s", full_path, e)
        return ""

    # ── Skip YAML frontmatter (between --- markers) ──
    body_text = content
    if content.startswith("---"):
        # Find the second ---
        idx = content.find("---", 3)
        if idx > 0:
            body_text = content[idx + 3:]

    # ── Extract content after '## 正文内容' ──
    match = re.search(r"##\s*正文内容\s*\n", body_text)
    if match:
        return body_text[match.end():].strip()

    # ── Fallback: find after first --- separator ──
    lines = body_text.strip().split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "---":
            remaining = "\n".join(lines[i + 1:]).strip()
            if remaining:
                return remaining

    # ── Last resort: return everything after metadata section ──
    return body_text.strip()


@router.get("/news/search")
async def search_news(
    keyword: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    min_importance: int = Query(0, ge=0, le=5),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("date"),
    sort_order: str = Query("desc"),
):
    offset = (page - 1) * page_size
    total = db_module.count_news(
        date_from=date_from, date_to=date_to,
        domain=domain, city=city, source=source,
    )
    items = db_module.search_news(
        keyword=keyword,
        domain=domain,
        city=city,
        source=source,
        min_importance=min_importance,
        date_from=date_from,
        date_to=date_to,
        limit=page_size,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/news/{news_id}")
async def get_news_detail(news_id: str):
    results = db_module.search_news(keyword=news_id, limit=1)
    if not results:
        # Try search by ID
        db = db_module.get_db()
        cur = db.execute("SELECT * FROM news_index WHERE id = ?", (news_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="News not found")
        if db.type == "sqlite":
            d = dict(row)
        else:
            d = dict(zip([c[0] for c in cur.description], row))
        import json
        for field in ("domain", "cities", "entities", "tags"):
            val = d.get(field, "[]")
            if isinstance(val, str):
                try:
                    d[field] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return ApiResponse(success=True, data=d)
    return ApiResponse(success=True, data=results[0])


@router.get("/news/{news_id}/content")
async def get_news_content(news_id: str):
    """Get full article body content for a news item."""
    # Look up the news item to get file_path
    db = db_module.get_db()
    cur = db.execute("SELECT file_path, title FROM news_index WHERE id = ?", (news_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="News not found")

    if db.type == "sqlite":
        file_path = row["file_path"]
        title = row["title"]
    else:
        d = dict(zip([c[0] for c in cur.description], row))
        file_path = d["file_path"]
        title = d["title"]

    content = _extract_article_body(file_path)

    return ApiResponse(
        success=True,
        data={
            "id": news_id,
            "title": title,
            "content": content,
            "word_count": len(content),
        },
    )
