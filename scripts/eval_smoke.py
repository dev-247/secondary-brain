from __future__ import annotations

import json
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from qdrant_client import QdrantClient
from rich.console import Console
from rich.table import Table

from scripts.config import ROOT
from scripts.ingest import ingest_vault
from scripts.search import hybrid_search

DEFAULT_VAULT = ROOT / "tests" / "fixtures" / "smoke_vault"
DEFAULT_CASES = ROOT / "tests" / "fixtures" / "smoke_queries.json"
DEFAULT_COLLECTION = "second_brain_smoke"
SMOKE_EMBED_DIMENSION = 4


@dataclass(frozen=True)
class SmokeCase:
    query: str
    expected_path: str


@dataclass(frozen=True)
class SmokeCaseResult:
    case: SmokeCase
    found_paths: list[str]

    @property
    def ok(self) -> bool:
        return self.case.expected_path in self.found_paths


@dataclass(frozen=True)
class SmokeEvalResult:
    case_results: list[SmokeCaseResult]

    @property
    def passed(self) -> int:
        return sum(1 for result in self.case_results if result.ok)

    @property
    def failed(self) -> int:
        return len(self.case_results) - self.passed

    @property
    def ok(self) -> bool:
        return self.failed == 0


def smoke_embedding(text: str) -> list[float]:
    buckets = [0.0] * SMOKE_EMBED_DIMENSION
    for index, char in enumerate(text.lower()):
        buckets[index % SMOKE_EMBED_DIMENSION] += float(ord(char) % 17)
    magnitude = sum(value * value for value in buckets) ** 0.5 or 1.0
    return [value / magnitude for value in buckets]


def load_cases(path: Path = DEFAULT_CASES) -> list[SmokeCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    return [
        SmokeCase(query=str(item["query"]), expected_path=str(item["expected_path"]))
        for item in raw_cases
    ]


def _run_with_isolated_qdrant(
    vault_root: Path,
    cases: list[SmokeCase],
    qdrant_path: Path,
    collection_name: str,
) -> SmokeEvalResult:
    client = QdrantClient(path=str(qdrant_path))

    with patch("scripts.qdrant_setup.QDRANT_MODE", "local"):
        with patch("scripts.qdrant_setup.QDRANT_PATH", qdrant_path):
            with patch("scripts.qdrant_setup.QDRANT_COLLECTION", collection_name):
                with patch("scripts.ingest.QDRANT_COLLECTION", collection_name):
                    with patch("scripts.search.QDRANT_COLLECTION", collection_name):
                        with patch("scripts.qdrant_setup.EMBED_DIMENSION", SMOKE_EMBED_DIMENSION):
                            with patch("scripts.qdrant_setup.get_client", return_value=client):
                                with patch("scripts.ingest.get_client", return_value=client):
                                    with patch("scripts.search.get_client", return_value=client):
                                        with patch("scripts.ingest.embed_text", side_effect=smoke_embedding):
                                            with patch("scripts.search.embed_text", side_effect=smoke_embedding):
                                                with redirect_stdout(StringIO()):
                                                    ingest_vault(
                                                        vault_root,
                                                        metadata_path=qdrant_path.parent / "metadata.sqlite",
                                                    )
                                                case_results: list[SmokeCaseResult] = []
                                                for case in cases:
                                                    results = hybrid_search(case.query, limit=3)
                                                    case_results.append(
                                                        SmokeCaseResult(
                                                            case=case,
                                                            found_paths=[result.path for result in results],
                                                        )
                                                    )
                                                return SmokeEvalResult(case_results)


def run_smoke_eval(
    *,
    vault_root: Path = DEFAULT_VAULT,
    cases: list[SmokeCase] | None = None,
    qdrant_path: Path | None = None,
    collection_name: str = DEFAULT_COLLECTION,
) -> SmokeEvalResult:
    cases = cases or load_cases()

    if qdrant_path is not None:
        return _run_with_isolated_qdrant(vault_root, cases, qdrant_path, collection_name)

    with tempfile.TemporaryDirectory() as directory:
        return _run_with_isolated_qdrant(
            vault_root=vault_root,
            cases=cases,
            qdrant_path=Path(directory) / "qdrant",
            collection_name=collection_name,
        )


def print_smoke_eval(console: Console | None = None) -> int:
    console = console or Console()
    result = run_smoke_eval()

    table = Table(title="Smoke Retrieval Evaluation")
    table.add_column("Status")
    table.add_column("Query", style="cyan")
    table.add_column("Expected")
    table.add_column("Found")

    for case_result in result.case_results:
        table.add_row(
            "[green]pass[/green]" if case_result.ok else "[red]fail[/red]",
            case_result.case.query,
            case_result.case.expected_path,
            ", ".join(case_result.found_paths) or "none",
        )

    console.print(table)
    console.print(f"\nPassed {result.passed}/{len(result.case_results)} smoke retrieval cases.")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(print_smoke_eval())
