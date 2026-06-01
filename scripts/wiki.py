from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from scripts.config import WIKI_DIR
from scripts.search import SearchResult, format_citation


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def _summary_sentence(content: str) -> str:
    collapsed = " ".join(content.split())
    sentence = re.split(r"(?<=[.!?])\s+", collapsed, maxsplit=1)[0]
    return sentence.strip()


def build_wiki_draft(topic: str, sources: list[SearchResult]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    lines = [
        "---",
        f"title: {topic}",
        "review_status: draft",
        "generated_by: second-brain",
        f"generated_at: {generated_at}",
        "---",
        "",
        f"# {topic}",
        "",
        "## Summary",
        "",
    ]

    if sources:
        for index, source in enumerate(sources, start=1):
            lines.append(f"- {_summary_sentence(source.content)} [{index}]")
    else:
        lines.append("- No source-backed summary could be generated.")

    lines.extend(["", "## Sources", ""])
    for index, source in enumerate(sources, start=1):
        lines.append(f"[{index}] {format_citation(source)}")

    lines.extend(
        [
            "",
            "## Review",
            "",
            "- Status: draft",
            "- Reviewer: unreviewed",
        ]
    )
    return "\n".join(lines) + "\n"


def write_wiki_draft(
    topic: str,
    sources: list[SearchResult],
    *,
    wiki_root: Path = WIKI_DIR,
) -> Path:
    drafts_dir = wiki_root / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    path = drafts_dir / f"{slugify(topic)}.md"
    path.write_text(build_wiki_draft(topic, sources), encoding="utf-8")
    return path
