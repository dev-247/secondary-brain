from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
from typing import Protocol

from qdrant_client import models

from scripts.config import QDRANT_COLLECTION
from scripts.embeddings import embed_text
from scripts.qdrant_setup import get_client


@dataclass
class SearchResult:
    content: str
    filename: str
    path: str
    heading: str
    chunk_index: int
    score: float
    fused_score: float = 0.0
    lexical_score: float = 0.0
    absolute_path: str = ""
    page_start: int | None = None
    page_end: int | None = None


class Reranker(Protocol):
    name: str

    def score(self, query: str, result: SearchResult) -> float:
        ...


def _query_terms(query: str) -> set[str]:
    return {term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 1}


def _keyword_overlap_score(query: str, content: str) -> float:
    query_terms = _query_terms(query)
    if not query_terms:
        return 0.0
    content_lower = content.lower()
    hits = sum(1 for term in query_terms if term in content_lower)
    return hits / len(query_terms)


def _is_definition_query(query: str) -> bool:
    normalized = " ".join(_query_terms(query))
    return (
        query.lower().strip().startswith(("what is", "what's", "define ", "explain "))
        or "what is" in query.lower()
        or normalized.startswith("define")
    )


def _definition_intro_boost(query: str, result: SearchResult) -> float:
    if not _is_definition_query(query) or result.chunk_index != 0:
        return 0.0
    terms = _query_terms(query)
    stem = PurePosixPath(result.path).stem.lower()
    filename_stem = PurePosixPath(result.filename).stem.lower()
    if stem in terms or filename_stem in terms:
        return 0.4
    return 0.0


class WeightedLexicalReranker:
    name = "weighted_lexical"

    def score(self, query: str, result: SearchResult) -> float:
        lexical_boost = _keyword_overlap_score(query, result.content)
        definition_boost = _definition_intro_boost(query, result)
        result.lexical_score = lexical_boost
        if result.fused_score == 0.0:
            result.fused_score = result.score
        return (result.fused_score * 0.75) + (lexical_boost * 0.15) + definition_boost


class LexicalOnlyReranker:
    name = "lexical_only"

    def score(self, query: str, result: SearchResult) -> float:
        lexical_score = _keyword_overlap_score(query, result.content)
        result.lexical_score = lexical_score
        if result.fused_score == 0.0:
            result.fused_score = result.score
        return lexical_score


def rerank(
    query: str,
    results: list[SearchResult],
    limit: int = 5,
    strategy: Reranker | None = None,
) -> list[SearchResult]:
    strategy = strategy or WeightedLexicalReranker()
    for result in results:
        result.score = strategy.score(query, result)
    ranked = sorted(results, key=lambda item: item.score, reverse=True)
    return ranked[:limit]


def hybrid_search(query: str, limit: int = 5, prefetch_limit: int = 20) -> list[SearchResult]:
    client = get_client()
    dense_vector = embed_text(query)

    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        prefetch=[
            models.Prefetch(query=dense_vector, using="dense", limit=prefetch_limit),
            models.Prefetch(
                query=models.Document(text=query, model="qdrant/bm25"),
                using="sparse",
                limit=prefetch_limit,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=prefetch_limit,
        with_payload=True,
    )

    results: list[SearchResult] = []
    for point in response.points:
        payload = point.payload or {}
        page_start = payload.get("page_start")
        page_end = payload.get("page_end")
        results.append(
            SearchResult(
                content=str(payload.get("content", "")),
                filename=str(payload.get("filename", "")),
                path=str(payload.get("path", "")),
                heading=str(payload.get("heading", "")),
                chunk_index=int(payload.get("chunk_index", 0)),
                score=float(point.score or 0.0),
                fused_score=float(point.score or 0.0),
                absolute_path=str(payload.get("absolute_path", "")),
                page_start=int(page_start) if page_start is not None else None,
                page_end=int(page_end) if page_end is not None else None,
            )
        )

    return rerank(query, results, limit=limit)


def format_citation(result: SearchResult) -> str:
    if result.page_start is not None:
        if result.page_end is not None and result.page_end != result.page_start:
            page_label = f"pages {result.page_start}-{result.page_end}"
        else:
            page_label = f"page {result.page_start}"
        location = f"{result.path}, {page_label}"
    else:
        location = f"{result.path}#{result.heading}" if result.heading else result.path
    return f"{result.filename} ({location}, chunk {result.chunk_index})"


def _preview(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."


def diagnostic_rows(
    results: list[SearchResult],
    *,
    preview_chars: int = 120,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rank, result in enumerate(results, start=1):
        rows.append(
            {
                "rank": str(rank),
                "score": f"{result.score:.4f}",
                "fused_score": f"{result.fused_score:.4f}",
                "lexical_score": f"{result.lexical_score:.4f}",
                "path": result.path,
                "heading": result.heading,
                "chunk": str(result.chunk_index),
                "citation": format_citation(result),
                "preview": _preview(result.content, preview_chars),
            }
        )
    return rows
