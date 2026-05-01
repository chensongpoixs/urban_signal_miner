"""Markdown report parser — converts report markdown to structured JSON sections.

Each report type has a dedicated parser that understands its section structure.
"""
import re
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"


class MarkdownParser:

    def parse(self, report_type: str, markdown: str) -> dict:
        parsers = {
            "weekly": self._parse_weekly,
            "monthly": self._parse_monthly,
            "quarterly": self._parse_quarterly,
            "special_city_compare": self._parse_city_compare,
            "special_causal_chain": self._parse_causal_chain,
        }
        parser = parsers.get(report_type)
        if not parser:
            return self._empty_result(report_type, markdown)
        return parser(markdown)

    # ── Metadata extraction ──

    def _extract_metadata(self, md: str) -> dict:
        """Extract header metadata lines like **周期**:, **生成时间**."""
        meta: dict[str, str] = {}
        # Match lines like: **周期**: 2026-04-27 ~ 2026-05-03
        meta_patterns = [
            (r"\*\*周期\*\*:\s*(.+)", "period"),
            (r"\*\*Cycle\*\*:\s*(.+)", "period"),
            (r"\*\*周期编号\*\*:\s*(.+)", "period_key"),
            (r"\*\*生成时间\*\*:\s*(.+)", "generated_at"),
            (r"\*\*Generated\*\*:\s*(.+)", "generated_at"),
            (r"\*\*新闻数量\*\*:\s*(\d+)", "news_count"),
            (r"\*\*News Count\*\*:\s*(\d+)", "news_count"),
            (r"\*\*数据范围\*\*:\s*(.+)", "data_range"),
            (r"\*\*Data Range\*\*:\s*(.+)", "data_range"),
            (r"\*\*分析方法\*\*:\s*(.+)", "method_note"),
            (r"\*\*Analyze Method\*\*:\s*(.+)", "method_note"),
            (r"\*\*相关新闻\*\*:\s*(\d+)", "news_count"),
            (r"\*\*Related News\*\*:\s*(\d+)", "news_count"),
        ]
        for pattern, key in meta_patterns:
            m = re.search(pattern, md)
            if m:
                meta[key] = m.group(1).strip()

        # Parse title from H1
        h1 = re.search(r"^# (.+)$", md, re.MULTILINE)
        title = h1.group(1).strip() if h1 else ""
        meta["title"] = title

        if "period" in meta:
            parts = meta["period"].split("~")
            meta["period_start"] = parts[0].strip()
            if len(parts) > 1:
                meta["period_end"] = parts[1].strip()
        elif "data_range" in meta:
            parts = meta["data_range"].replace("最近", "").replace("Last", "").strip()
            meta["period_start"] = parts

        return meta

    # ── Section splitting ──

    def _split_sections(self, text: str) -> list[tuple[str, str]]:
        """Split markdown by ## or ### section headers. Returns [(title, content), ...]."""
        # Remove frontmatter (--- to ---)
        text = re.sub(r"^---\n.*?---\n", "", text, flags=re.DOTALL)
        # Remove header block (lines with **key**: value)
        header_end = 0
        for i, line in enumerate(text.split("\n")[:20]):
            if line.startswith("---") and i > 2:
                header_end = i + 1
                break
        text_lines = text.split("\n")[header_end:]

        sections: list[tuple[str, str]] = []
        current_title = ""
        current_lines: list[str] = []

        for line in text_lines:
            m = re.match(r"^(#{2,3})\s+(.+)", line)
            if m:
                if current_title or current_lines:
                    content = "\n".join(current_lines).strip()
                    sections.append((current_title, content))
                current_title = m.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)

        if current_title or current_lines:
            sections.append((current_title, "\n".join(current_lines).strip()))

        return sections

    def _section_id(self, title: str) -> str:
        """Generate a stable section ID from title."""
        title = re.sub(r"[一二三四五六七八九十]+、", "", title)
        title = re.sub(r"[#\d]+\.\s*", "", title)
        return re.sub(r"[^\w]+", "_", title.strip()).strip("_").lower()[:40]

    def _section_type(self, title: str) -> str:
        """Infer section type from title keywords."""
        t = title.lower()
        if any(kw in t for kw in ["top", "事件", "event", "排名"]):
            return "ranked_list"
        if any(kw in t for kw in ["领域", "domain", "动态", "dynamic"]):
            return "domain_summary"
        if any(kw in t for kw in ["趋势", "trend", "信号", "signal", "预判", "forecast"]):
            return "trend"
        if any(kw in t for kw in ["城市", "city"]):
            return "city_analysis"
        if any(kw in t for kw in ["因果", "causal", "链", "chain"]):
            return "causal_chain"
        if any(kw in t for kw in ["机会", "opportunity", "地图", "map"]):
            return "opportunity"
        if any(kw in t for kw in ["规律", "rule", "运行", "mechanism"]):
            return "mechanism"
        if any(kw in t for kw in ["叙事", "narrative", "核心", "theme"]):
            return "narrative"
        if any(kw in t for kw in ["盲区", "blind", "建议", "suggestion"]):
            return "insight"
        if any(kw in t for kw in ["关注", "watch", "outlook", "下周", "下月", "下季度"]):
            return "outlook"
        return "text"

    def _parse_items(self, content: str) -> list[dict]:
        """Parse list items from content."""
        items: list[dict] = []
        current = None
        for line in content.split("\n"):
            li = re.match(r"^(?:[-*]|\d+[.、])\s+(.+)", line.strip())
            if li:
                if current:
                    items.append(current)
                item_text = li.group(1)
                # Extract importance stars if present
                stars = len(re.findall(r"★", item_text))
                item_text = re.sub(r"★+", "", item_text).strip()
                current = {"content": item_text, "importance": stars}
            elif current and line.strip():
                # Continuation line
                current["content"] += " " + line.strip()
        if current:
            items.append(current)
        return items

    def _parse_table(self, content: str) -> list[dict]:
        """Parse markdown table to list of dicts."""
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if len(lines) < 3:
            return []
        header_match = re.findall(r"\|([^|]+)", lines[0])
        headers = [h.strip() for h in header_match]
        separator = lines[1]
        if not all(c in "|-: " for c in separator):
            return []
        rows = []
        for line in lines[2:]:
            cells = re.findall(r"\|([^|]+)", line)
            if len(cells) >= len(headers):
                row = {}
                for i, h in enumerate(headers):
                    row[h] = cells[i].strip() if i < len(cells) else ""
                rows.append(row)
        return rows

    # ── Type-specific parsers ──

    def _parse_weekly(self, md: str) -> dict:
        meta = self._extract_metadata(md)
        sections = []
        for title, content in self._split_sections(md):
            sec_type = self._section_type(title)
            data: dict[str, Any] = {
                "id": self._section_id(title),
                "title": title,
                "type": sec_type,
            }
            if sec_type in ("ranked_list",):
                data["items"] = self._parse_items(content)
                data["content"] = ""
            else:
                data["content"] = content
                data["items"] = None
            sections.append(data)

        return {
            "report_type": "weekly",
            "period_key": meta.get("period_key", ""),
            "file_path": "",
            "metadata": {
                "title": meta.get("title", ""),
                "period_start": meta.get("period_start", ""),
                "period_end": meta.get("period_end", ""),
                "generated_at": meta.get("generated_at", ""),
                "news_count": int(meta.get("news_count", 0)),
                "method_note": meta.get("method_note", ""),
            },
            "sections": sections,
            "key_findings": self._extract_key_findings_from_md(md),
            "raw_markdown": md,
        }

    def _parse_monthly(self, md: str) -> dict:
        return self._parse_weekly(md)  # Same structure, reuse

    def _parse_quarterly(self, md: str) -> dict:
        meta = self._extract_metadata(md)
        sections = []
        for title, content in self._split_sections(md):
            sec_type = self._section_type(title)
            data: dict[str, Any] = {
                "id": self._section_id(title),
                "title": title,
                "type": sec_type,
            }
            if sec_type == "causal_chain":
                data["items"] = self._parse_items(content)
                data["content"] = ""
            elif sec_type == "opportunity":
                table = self._parse_table(content)
                data["items"] = table if table else None
                data["content"] = content if not table else ""
            elif sec_type == "mechanism":
                data["items"] = self._parse_items(content)
                data["content"] = ""
            else:
                data["content"] = content
                data["items"] = self._parse_items(content) if self._parse_items(content) else None
            sections.append(data)

        return {
            "report_type": "quarterly",
            "period_key": meta.get("period_key", ""),
            "file_path": "",
            "metadata": {
                "title": meta.get("title", ""),
                "period_start": meta.get("period_start", ""),
                "period_end": meta.get("period_end", ""),
                "generated_at": meta.get("generated_at", ""),
                "news_count": int(meta.get("news_count", 0)),
                "method_note": meta.get("method_note", ""),
            },
            "sections": sections,
            "key_findings": self._extract_key_findings_from_md(md),
            "raw_markdown": md,
        }

    def _parse_city_compare(self, md: str) -> dict:
        meta = self._extract_metadata(md)
        sections = []
        for title, content in self._split_sections(md):
            sec_type = self._section_type(title)
            table = self._parse_table(content) if "表" in title or "|" in content else None
            sections.append({
                "id": self._section_id(title),
                "title": title,
                "type": sec_type,
                "content": content,
                "items": table,
            })

        return {
            "report_type": "special_city_compare",
            "period_key": meta.get("period_key", ""),
            "file_path": "",
            "metadata": {
                "title": meta.get("title", ""),
                "period_start": meta.get("period_start", ""),
                "period_end": meta.get("period_end", ""),
                "generated_at": meta.get("generated_at", ""),
                "news_count": int(meta.get("news_count", 0)),
                "method_note": meta.get("method_note", ""),
            },
            "sections": sections,
            "key_findings": self._extract_key_findings_from_md(md),
            "raw_markdown": md,
        }

    def _parse_causal_chain(self, md: str) -> dict:
        meta = self._extract_metadata(md)
        sections = []
        for title, content in self._split_sections(md):
            sec_type = self._section_type(title)
            sections.append({
                "id": self._section_id(title),
                "title": title,
                "type": sec_type,
                "content": content,
                "items": self._parse_items(content) if sec_type in ("causal_chain", "ranked_list") else None,
            })

        return {
            "report_type": "special_causal_chain",
            "period_key": meta.get("period_key", ""),
            "file_path": "",
            "metadata": {
                "title": meta.get("title", ""),
                "period_start": meta.get("period_start", ""),
                "period_end": meta.get("period_end", ""),
                "generated_at": meta.get("generated_at", ""),
                "news_count": int(meta.get("news_count", 0)),
                "method_note": meta.get("method_note", ""),
            },
            "sections": sections,
            "key_findings": self._extract_key_findings_from_md(md),
            "raw_markdown": md,
        }

    def _extract_key_findings_from_md(self, md: str) -> str:
        """Extract first substantive paragraph from report body."""
        from utils.db import extract_key_findings
        return extract_key_findings(md, max_chars=500)

    def _empty_result(self, report_type: str, md: str) -> dict:
        return {
            "report_type": report_type,
            "period_key": "",
            "file_path": "",
            "metadata": {
                "title": "",
                "period_start": "",
                "period_end": "",
                "generated_at": "",
                "news_count": 0,
                "method_note": "",
            },
            "sections": [],
            "key_findings": "",
            "raw_markdown": md,
        }
