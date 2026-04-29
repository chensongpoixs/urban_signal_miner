#!/usr/bin/env python3
"""
AI 新闻分类/打标脚本。

读取 news-corpus/ 中未被增强的 .md 文件，用 Claude 进行：
1. 去重判断
2. 领域分类（可多选）
3. 城市关联（可多选）
4. 实体提取（公司/人物/政策/技术/产品）
5. 标签打标
6. 重要性评分（1-5）
7. 摘要生成
8. 在文件顶部插入 YAML frontmatter
"""
import sys
import re
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from utils.config_loader import get_source_weights, get_cities, get_domains, get_city_keywords, get_settings
from utils.llm_client import chat_structured
from utils.db import init_db, insert_news, mark_file_processed, is_file_processed
from utils.file_utils import get_unenhanced_files
from utils.logging_config import setup_logging

logger = setup_logging("classify", "classify.log")

PROJECT_DIR = Path(__file__).parent.parent
NEWS_DIR = PROJECT_DIR / "news-corpus"

# ── Pydantic 输出模型 ──────────────────────────────────

class Entity(BaseModel):
    name: str
    type: str  # company, person, policy, technology, product, event, organization

class NewsClassification(BaseModel):
    domain: list[str] = Field(default_factory=list,
        description="领域分类: 科技/AI, 经济/金融, 政治/国际关系, 社会/民生, 综合/其他")
    cities: list[str] = Field(default_factory=list,
        description="涉及的城市: 北京, 上海, 深圳, 苏州, 南京, 淮安")
    entities: list[Entity] = Field(default_factory=list,
        description="关键实体列表")
    tags: list[str] = Field(default_factory=list,
        description="标签关键词，3-8个")
    importance: int = Field(default=3, ge=1, le=5,
        description="重要性 1-5: 1=纯娱乐八卦 2=一般信息 3=有价值 4=重要趋势信号 5=重大事件/转折点")
    ai_summary: str = Field(default="",
        description="50-150字精炼摘要")
    ai_why_matters: str = Field(default="",
        description="这条新闻为什么重要？可能引发什么连锁反应？若重要度<3可留空")
    is_duplicate: bool = Field(default=False,
        description="是否与已知新闻重复")
    quality_pass: bool = Field(default=True,
        description="是否通过质量筛选（纯广告/纯八卦/无实质内容=不通过）")

# ── 去重 & 预筛 ────────────────────────────────────────

def check_title_similarity(title: str, date_str: str) -> bool:
    """检查标题与数据库中同日期已有新闻的相似度。返回 True 表示重复。"""
    from difflib import SequenceMatcher
    from utils.db import search_news

    threshold = get_settings().get("dedup", {}).get("title_similarity_threshold", 0.8)
    if not title:
        return False

    existing = search_news(date_from=date_str, date_to=date_str, limit=200)
    for item in existing:
        existing_title = item.get("title", "")
        if not existing_title:
            continue
        ratio = SequenceMatcher(None, title, existing_title).ratio()
        if ratio >= threshold:
            logger.info("Title dup(%.2f): %s ~ %s", ratio, title[:40], existing_title[:40])
            return True
    return False


def prefilter_cities(title: str, body: str) -> list[str]:
    """用关键词预筛城市，返回可能相关的城市列表。缩小 LLM 候选范围。"""
    from utils.config_loader import get_city_keywords

    text = f"{title} {body}"
    city_keywords = get_city_keywords()
    matched = []
    for city_name, keywords in city_keywords.items():
        for kw in keywords:
            if kw in text:
                matched.append(city_name)
                break
    return matched


# ── 解析原始 Markdown ──────────────────────────────────

def parse_raw_md(filepath: Path, body_chars: int = 3000) -> Optional[dict]:
    """解析原始 Markdown 文件，提取元数据和正文。"""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Cannot read file %s: %s", filepath.name, e)
        return None

    # 如果已有 frontmatter，跳过
    if content.strip().startswith("---"):
        return None

    lines = content.strip().split("\n")
    if not lines:
        return None

    meta = {}
    title = ""
    body_start = 0

    # 解析标题 (H1)
    if lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body_start = 1

    # 解析元数据行 (以 - ** 开头)
    meta_lines = []
    for i, line in enumerate(lines[body_start:], start=body_start):
        if line.startswith("- **") and "**:" in line:
            meta_lines.append(line)
        elif line.startswith("---"):
            break
        elif line and not line.startswith("- "):
            break

    for line in meta_lines:
        match = re.match(r"-\s*\*\*(.+?)\*\*:\s*(.+)", line)
        if match:
            key = match.group(1).strip()
            val = match.group(2).strip()
            meta[key] = val

    # 提取正文（跳过元数据区和分隔线）
    body_lines = []
    in_body = False
    for line in lines[body_start + len(meta_lines):]:
        if line.startswith("## 正文内容") or line.startswith("---"):
            in_body = True
            continue
        if in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    # 截断过长正文
    if len(body) > body_chars:
        body = body[:body_chars] + "..."

    return {
        "title": title,
        "source": meta.get("来源平台", ""),
        "rank": meta.get("排名", ""),
        "source_url": meta.get("原文链接", ""),
        "crawl_time": meta.get("抓取时间", ""),
        "body": body,
        "filepath": filepath,
        "word_count": len(body),
    }


def extract_date_from_path(filepath: Path) -> str:
    """从文件路径提取日期。路径格式: /news-corpus/20260428/source/file.md"""
    parts = filepath.parts
    for p in parts:
        if p.isdigit() and len(p) == 8:
            return f"{p[:4]}-{p[4:6]}-{p[6:8]}"
    return datetime.now().strftime("%Y-%m-%d")


# ── 构建 Prompt ────────────────────────────────────────

def build_domain_list() -> str:
    domains = get_domains()
    return "\n".join(f"- {d['name']}" for d in domains)


def build_city_list() -> str:
    cities = get_cities()
    return "\n".join(f"- {c['name']} (关键词: {', '.join(c['keywords'][:5])}...)" for c in cities)


def build_classify_prompt(article: dict) -> str:
    return f"""标题：{article['title']}
来源：{article['source']}
日期：{extract_date_from_path(article['filepath'])}
排名：{article.get('rank', 'N/A')}

正文：
{article['body']}

请对以上新闻进行分析，返回严格的 JSON 格式。"""


CLASSIFY_SYSTEM = """你是专业新闻分析助手。根据以下标准分析新闻：

## 领域分类体系
{domains}

## 城市关键词
{cities}

## 重要性评分标准
1 = 纯娱乐八卦/广告，无分析价值
2 = 一般信息，知道即可
3 = 有一定价值的信息
4 = 重要的趋势信号/关键事件
5 = 重大事件/转折点，可能引发连锁反应

## 标签规则
- 每条约3-8个标签
- 标签简洁准确，如"自动驾驶""A股""中美关系""半导体"
- 优先使用专业术语而非泛词

## 实体提取
- company: 公司/企业
- person: 人物
- policy: 政策/法规
- technology: 技术/标准
- product: 产品/服务
- organization: 机构/组织

## 去重规则
- 如果标题和正文与其他常见新闻高度重复（如多个源报道同一事件），标记 is_duplicate=true
- 同一天内同一主题的多篇报道只保留一篇高质量的

## 质量筛选
- 纯广告、纯娱乐八卦、无实质内容的标记 quality_pass=false

必须以有效 JSON 格式返回，不要有任何其他文本。"""


# ── 增强文件 ────────────────────────────────────────────

def enhance_file(filepath: Path, result: NewsClassification, article: dict):
    """在 Markdown 文件顶部插入 YAML frontmatter。"""
    date_str = extract_date_from_path(filepath)
    source = article.get("source", filepath.parent.name)
    rank = article.get("rank", "")

    # 生成 ID
    try:
        rank_int = int(rank.replace("#", ""))
    except (ValueError, AttributeError):
        rank_int = 99
    id_str = f"{date_str.replace('-', '')}-{source}-{rank_int:03d}"

    # 来源名称
    sources = get_source_weights()
    source_info = sources.get(source, {})
    source_name = source_info.get("name", source)

    # 预先计算需要在 f-string 中使用的值（f-string 内不能有反斜杠）
    safe_title = article['title'].replace('"', '\\"')
    safe_summary = result.ai_summary.replace('"', '\\"')
    safe_why = result.ai_why_matters.replace('"', '\\"')
    domain_json = json.dumps(result.domain, ensure_ascii=False)
    cities_json = json.dumps(result.cities, ensure_ascii=False)
    entities_json = json.dumps([e.model_dump() for e in result.entities], ensure_ascii=False)
    tags_json = json.dumps(result.tags, ensure_ascii=False)

    frontmatter = f"""---
id: "{id_str}"
date: "{date_str}"
source: "{source}"
source_name: "{source_name}"
source_url: "{article.get('source_url', '')}"
rank: {rank_int}
title: "{safe_title}"
domain: {domain_json}
cities: {cities_json}
entities: {entities_json}
tags: {tags_json}
importance: {result.importance}
ai_summary: "{safe_summary}"
ai_why_matters: "{safe_why}"
---

"""

    try:
        original = filepath.read_text(encoding="utf-8")
        new_content = frontmatter + original.lstrip("\n")
        filepath.write_text(new_content, encoding="utf-8")
        logger.info("Enhanced: %s [importance=%d] %s", id_str, result.importance, result.domain)

        # 写入 SQLite 索引
        rel_path = str(filepath.relative_to(NEWS_DIR))
        insert_news({
            "id": id_str,
            "date": date_str,
            "source": source,
            "source_name": source_name,
            "source_url": article.get("source_url", ""),
            "rank": rank_int,
            "title": article["title"],
            "domain": result.domain,
            "cities": result.cities,
            "entities": [e.model_dump() for e in result.entities],
            "tags": result.tags,
            "importance": result.importance,
            "ai_summary": result.ai_summary,
            "ai_why_matters": result.ai_why_matters,
            "file_path": rel_path,
            "word_count": article.get("word_count", 0),
        })
    except Exception as e:
        logger.error("Enhance failed %s: %s", filepath.name, e)


# ── 主处理流程 ──────────────────────────────────────────

def process_files(filepaths: list[Path], dry_run: bool = False):
    """处理文件列表，增强每个文件。支持断点续跑（跳过已处理文件）。"""
    settings = get_settings()

    # 过滤已处理的（断点续跑）
    str_paths = [str(p.relative_to(NEWS_DIR)) for p in filepaths]
    unprocessed = []
    skipped_count = 0
    for p, sp in zip(filepaths, str_paths):
        if not is_file_processed(sp):
            unprocessed.append(p)
        else:
            skipped_count += 1

    if skipped_count > 0:
        logger.info("Checkpoint resume: %d files already processed, skipping", skipped_count)
    logger.info("Total %d files, %d pending", len(filepaths), len(unprocessed))

    if dry_run:
        logger.info("[DRY RUN] Will process the following files (first 50):")
        for p in unprocessed[:50]:
            logger.info("  %s", p.relative_to(NEWS_DIR))
        return

    # 可配置参数
    batch_size = settings.get("llm_limits", {}).get("classify_batch_size", 30)
    interval = settings.get("llm_limits", {}).get("classify_interval_seconds", 1)
    body_chars = settings.get("llm_limits", {}).get("classify_body_chars", 3000)
    total = len(unprocessed)

    from tqdm import tqdm

    pbar = tqdm(total=total, desc="AI 打标", unit="条",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")

    for batch_start in range(0, total, batch_size):
        batch = unprocessed[batch_start:batch_start + batch_size]

        # 解析所有文件
        articles = []
        for fp in batch:
            article = parse_raw_md(fp, body_chars=body_chars)
            if article:
                articles.append(article)

        if not articles:
            pbar.update(len(batch))
            continue

        # 构建带领域/城市信息的 system prompt
        system = CLASSIFY_SYSTEM.format(
            domains=build_domain_list(),
            cities=build_city_list(),
        )

        # 逐条调用
        for article in articles:
            try:
                date_str = extract_date_from_path(article["filepath"])
                title = article["title"]

                # B2: 标题相似度预筛
                if check_title_similarity(title, date_str):
                    rel = article["filepath"].relative_to(NEWS_DIR)
                    mark_file_processed(str(rel))
                    tqdm.write(f"⊘ Dup: {title[:50]}")
                    pbar.update(1)
                    continue

                # B3: 城市关键词预筛，注入 prompt
                city_hints = prefilter_cities(title, article.get("body", ""))
                prompt = build_classify_prompt(article)
                if city_hints:
                    prompt += f"\n\n提示：以下城市的关键词在文中出现，请重点关注: {', '.join(city_hints)}"

                result = chat_structured(system, prompt, NewsClassification)

                if result.is_duplicate or not result.quality_pass:
                    rel = article["filepath"].relative_to(NEWS_DIR)
                    tqdm.write(f"⊘ Skip: {rel.name[:50]} (dup/low quality)")
                    mark_file_processed(str(rel))
                    pbar.update(1)
                    continue

                enhance_file(article["filepath"], result, article)
                mark_file_processed(str(article["filepath"].relative_to(NEWS_DIR)))
                pbar.update(1)
                tqdm.write(f"OK ★{result.importance} {title[:60]}")

            except Exception as e:
                logger.error("Classify failed %s: %s", article["filepath"].name, e)
                # 不标记为已处理，下次重试（断点续跑）
                pbar.update(1)

            # API 速率限制
            if interval > 0:
                time.sleep(interval)

    pbar.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI 新闻分类增强")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode, no file modification")
    parser.add_argument("--files", nargs="*", help="Specific files (optional, scan all if omitted)")
    parser.add_argument("--limit", type=int, default=0, help="Max files to process (for testing)")
    args = parser.parse_args()

    init_db()

    if args.files:
        filepaths = [Path(f) for f in args.files]
    else:
        filepaths = get_unenhanced_files(NEWS_DIR)

    if args.limit > 0:
        filepaths = filepaths[:args.limit]

    logger.info("=" * 50)
    logger.info("News classify started")
    logger.info("Files to scan: %d", len(filepaths))

    process_files(filepaths, dry_run=args.dry_run)
    logger.info("News classify completed")
