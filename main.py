from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from scripts.audit import audit_wiki, print_audit_report
from scripts.config import VAULT_DIR, WIKI_DIR
from scripts.ingest import ingest_vault
from scripts.qdrant_setup import check_qdrant_health, qdrant_status_label
from scripts.router import synthesize_answer
from scripts.search import format_citation, hybrid_search

console = Console()


def cmd_status(_: argparse.Namespace) -> int:
    qdrant_ok = check_qdrant_health()
    vault_files = len(list(VAULT_DIR.rglob("*"))) if VAULT_DIR.exists() else 0
    wiki_files = len(list(WIKI_DIR.rglob("*.md"))) if WIKI_DIR.exists() else 0

    console.print(Panel(
        f"Qdrant: {'[green]ready[/green]' if qdrant_ok else '[red]down[/red]'} ({qdrant_status_label()})\n"
        f"Vault: {VAULT_DIR}\n"
        f"Wiki: {WIKI_DIR}\n"
        f"Vault entries: {vault_files}\n"
        f"Wiki articles: {wiki_files}",
        title="Second Brain Status",
    ))
    return 0 if qdrant_ok else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    root = Path(args.path).resolve() if args.path else VAULT_DIR
    try:
        stats = ingest_vault(root)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    console.print(
        f"[green]Ingested {stats['chunks']} chunks from {stats['files']} files.[/green]"
    )
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    if not check_qdrant_health():
        console.print("[red]Qdrant is not running. Start it with: docker compose up -d[/red]")
        return 1

    results = hybrid_search(args.query, limit=args.limit)
    if not results:
        console.print("[yellow]No information found in your knowledge base.[/yellow]")
        return 0

    try:
        answer, mode = synthesize_answer(
            args.query,
            results,
            force_deep=args.deep,
            mode="deep" if args.deep else ("fast" if args.fast else None),
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    console.print(Panel(Markdown(answer), title=f"Answer ({mode} mode)", border_style="green"))

    console.print("\n[bold]Sources[/bold]")
    for index, result in enumerate(results, start=1):
        citation = format_citation(result)
        link = result.absolute_path or str(VAULT_DIR / result.path)
        console.print(f"  [{index}] [link={link}]{citation}[/link]")

    return 0


def cmd_audit(_: argparse.Namespace) -> int:
    print_audit_report(audit_wiki())
    return 0


def cmd_chat(_: argparse.Namespace) -> int:
    if not check_qdrant_health():
        console.print("[red]Qdrant is not running. Start it with: docker compose up -d[/red]")
        return 1

    console.print("[bold]Second Brain[/bold] — ask questions about your vault. Type 'exit' to quit.\n")
    while True:
        try:
            query = console.input("[cyan]You[/cyan]: ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nGoodbye.")
            return 0

        if not query:
            continue
        if query.lower() in {"exit", "quit", "q"}:
            console.print("Goodbye.")
            return 0

        results = hybrid_search(query)
        if not results:
            console.print("[yellow]No information found in your knowledge base.[/yellow]\n")
            continue

        answer, mode = synthesize_answer(query, results)
        console.print(Panel(Markdown(answer), title=f"Answer ({mode})", border_style="green"))

        console.print("[bold]Sources[/bold]")
        for index, result in enumerate(results, start=1):
            console.print(f"  [{index}] {format_citation(result)}")
        console.print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Personal Second Brain — local-first knowledge assistant",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Check infrastructure status")
    status_parser.set_defaults(func=cmd_status)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest files from vault into Qdrant")
    ingest_parser.add_argument("--path", help="Vault directory (default: ./vault)")
    ingest_parser.set_defaults(func=cmd_ingest)

    ask_parser = subparsers.add_parser("ask", help="Ask a single question")
    ask_parser.add_argument("query", help="Your question")
    ask_parser.add_argument("--deep", action="store_true", help="Force cloud reasoning via OpenRouter")
    ask_parser.add_argument("--fast", action="store_true", help="Force local Ollama reasoning")
    ask_parser.add_argument("--limit", type=int, default=5, help="Number of source chunks to retrieve")
    ask_parser.set_defaults(func=cmd_ask)

    audit_parser = subparsers.add_parser("audit", help="Run wiki health audit")
    audit_parser.set_defaults(func=cmd_audit)

    chat_parser = subparsers.add_parser("chat", help="Interactive Q&A loop")
    chat_parser.set_defaults(func=cmd_chat)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
