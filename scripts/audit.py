from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from scripts.config import QDRANT_COLLECTION, WIKI_DIR
from scripts.qdrant_setup import check_qdrant_health, get_client

console = Console()
STALE_DAYS = 90


def _wiki_files(root: Path | None = None) -> list[Path]:
    root = root or WIKI_DIR
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


def audit_wiki(root: Path | None = None) -> dict[str, object]:
    root = root or WIKI_DIR
    root.mkdir(parents=True, exist_ok=True)
    files = _wiki_files(root)
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)

    stale: list[str] = []
    topics: list[str] = []
    for path in files:
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        relative = path.relative_to(root).as_posix()
        topics.append(relative)
        if modified < cutoff:
            stale.append(relative)

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
    table.add_row("Stale articles (>90d)", str(len(report["stale_files"])))
    console.print(table)

    stale_files = report["stale_files"]
    if stale_files:
        console.print("\n[yellow]Stale wiki content:[/yellow]")
        for item in stale_files:
            console.print(f"  - {item}")

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
