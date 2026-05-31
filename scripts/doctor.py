from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from scripts.config import OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL, OPENROUTER_API_KEY, ROOT
from scripts.qdrant_setup import check_qdrant_health, qdrant_status_label

REQUIRED_OLLAMA_MODELS = (OLLAMA_EMBED_MODEL, OLLAMA_CHAT_MODEL)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _run(command: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def parse_ollama_models(output: str) -> set[str]:
    models: set[str] = set()
    for line in output.splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        models.add(name)
        if ":" in name:
            models.add(name.split(":", 1)[0])
    return models


def missing_models(installed: set[str]) -> list[str]:
    return [model for model in REQUIRED_OLLAMA_MODELS if model not in installed]


def collect_checks() -> list[Check]:
    checks: list[Check] = []

    checks.append(
        Check(
            "Python",
            sys.version_info >= (3, 12),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )

    uv_path = shutil.which("uv")
    checks.append(Check("uv", uv_path is not None, uv_path or "not found"))

    env_path = ROOT / ".env"
    checks.append(Check(".env", env_path.exists(), str(env_path) if env_path.exists() else "missing"))

    qdrant_ok = check_qdrant_health()
    checks.append(Check("Qdrant", qdrant_ok, qdrant_status_label()))

    docker_path = shutil.which("docker")
    checks.append(
        Check(
            "Docker",
            docker_path is not None,
            docker_path or "not installed; embedded Qdrant mode is enough for local development",
            required=False,
        )
    )

    ollama_path = shutil.which("ollama")
    checks.append(Check("Ollama CLI", ollama_path is not None, ollama_path or "not found"))

    if ollama_path:
        result = _run(["ollama", "list"])
        if result and result.returncode == 0:
            installed = parse_ollama_models(result.stdout)
            missing = missing_models(installed)
            detail = "installed: " + ", ".join(sorted(installed))
            checks.append(Check("Ollama models", not missing, detail if not missing else "missing: " + ", ".join(missing)))
        else:
            checks.append(Check("Ollama models", False, "cannot reach Ollama; start the Ollama app/service"))

    checks.append(
        Check(
            "OpenRouter key",
            bool(OPENROUTER_API_KEY),
            "configured" if OPENROUTER_API_KEY else "not configured; only needed for deep mode",
            required=False,
        )
    )

    return checks


def print_doctor_report(console: Console | None = None) -> int:
    console = console or Console()
    checks = collect_checks()
    table = Table(title="Second Brain Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    for check in checks:
        status = "[green]ready[/green]" if check.ok else ("[yellow]optional[/yellow]" if not check.required else "[red]missing[/red]")
        table.add_row(check.name, status, check.detail)

    console.print(table)

    missing_required = [check for check in checks if check.required and not check.ok]
    if missing_required:
        console.print("\n[red]Required prerequisites are missing.[/red]")
        return 1

    console.print("\n[green]Required prerequisites are ready.[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(print_doctor_report())
