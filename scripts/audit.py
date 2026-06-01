from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from rich.console import Console
from rich.table import Table

from scripts.config import METADATA_DB_PATH, QDRANT_COLLECTION, WIKI_DIR
from scripts.metadata import SourceRecord, list_source_records
from scripts.qdrant_setup import check_qdrant_health, get_client

console = Console()
STALE_DAYS = 90


def _wiki_files(root: Path | None = None) -> list[Path]:
    root = root or WIKI_DIR
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def _review_status(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return "unknown"
    lines = text.splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("review_status:"):
            return line.split(":", 1)[1].strip() or "unknown"
    return "unknown"


def _topic_tokens(path: str) -> set[str]:
    stem = Path(path).stem.lower()
    tokens = set(re.findall(r"[a-z0-9]+", stem))
    return {token for token in tokens if len(token) > 2}


def _related_newer_sources(
    *,
    wiki_path: Path,
    relative_path: str,
    records: list[SourceRecord],
    limit: int = 3,
) -> list[str]:
    wiki_tokens = _topic_tokens(relative_path)
    if not wiki_tokens:
        return []

    wiki_modified_ns = wiki_path.stat().st_mtime_ns
    matches: list[SourceRecord] = []
    required_overlap = 1 if len(wiki_tokens) == 1 else 2
    for record in records:
        if record.modified_ns <= wiki_modified_ns:
            continue
        source_tokens = _topic_tokens(record.path)
        if len(wiki_tokens & source_tokens) >= required_overlap:
            matches.append(record)

    matches.sort(key=lambda record: (-record.modified_ns, record.path))
    return [record.path for record in matches[:limit]]


def audit_wiki(
    root: Path | None = None,
    *,
    metadata_path: Path = METADATA_DB_PATH,
) -> dict[str, object]:
    root = root or WIKI_DIR
    root.mkdir(parents=True, exist_ok=True)
    files = _wiki_files(root)
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    source_records = list_source_records(metadata_path)

    stale: list[str] = []
    topics: list[str] = []
    draft_files: list[str] = []
    reviewed_files: list[str] = []
    refresh_suggestions: list[dict[str, object]] = []
    for path in files:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        relative = path.relative_to(root).as_posix()
        topics.append(relative)
        status = _review_status(path)
        if status == "draft" or relative.startswith("drafts/"):
            draft_files.append(relative)
        elif status == "reviewed":
            reviewed_files.append(relative)
        if modified < cutoff:
            stale.append(relative)
            sources = _related_newer_sources(
                wiki_path=path,
                relative_path=relative,
                records=source_records,
            )
            if sources:
                refresh_suggestions.append({"wiki": relative, "sources": sources})

    qdrant_ok = check_qdrant_health()
    indexed_chunks = 0
    if qdrant_ok:
        try:
            info = get_client().get_collection(QDRANT_COLLECTION)
            indexed_chunks = info.points_count or 0
        except Exception:
            indexed_chunks = 0

    return {
        "wiki_files": len(files),
        "stale_files": stale,
        "topics": topics,
        "draft_files": draft_files,
        "reviewed_files": reviewed_files,
        "draft_count": len(draft_files),
        "reviewed_count": len(reviewed_files),
        "refresh_suggestions": refresh_suggestions,
        "indexed_chunks": indexed_chunks,
        "qdrant_ok": qdrant_ok,
    }


def print_audit_report(report: dict[str, object]) -> None:
    table = Table(title="Second Brain Audit")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Qdrant healthy", "yes" if report["qdrant_ok"] else "no")
    table.add_row("Indexed chunks", str(report["indexed_chunks"]))
    table.add_row("Wiki articles", str(report["wiki_files"]))
    table.add_row("Draft wiki pages", str(report["draft_count"]))
    table.add_row("Reviewed wiki pages", str(report["reviewed_count"]))
    table.add_row("Stale articles (>90d)", str(len(report["stale_files"])))
    table.add_row("Refresh suggestions", str(len(report["refresh_suggestions"])))
    console.print(table)

    stale_files = report["stale_files"]
    if stale_files:
        console.print("\n[yellow]Stale wiki content:[/yellow]")
        for item in stale_files:
            console.print(f"  - {item}")

    draft_files = report["draft_files"]
    if draft_files:
        console.print("\n[yellow]Draft wiki pages awaiting review:[/yellow]")
        for item in draft_files:
            console.print(f"  - {item}")

    refresh_suggestions = report["refresh_suggestions"]
    if refresh_suggestions:
        console.print("\n[yellow]Wiki pages that may need refresh:[/yellow]")
        for item in refresh_suggestions:
            sources = ", ".join(item["sources"])
            console.print(f"  - {item['wiki']} from {sources}")

    topics = report["topics"]
    if not topics:
        console.print(
            "\n[dim]No wiki articles yet. Generated summaries can be written to wiki/ over time.[/dim]"
        )
    elif len(topics) < 5:
        console.print("\n[cyan]Suggested new topics:[/cyan]")
        console.print("  - Build a reading list index from vault sources")
        console.print("  - Create a glossary of recurring concepts in your notes")


if __name__ == "__main__":
    print_audit_report(audit_wiki())
