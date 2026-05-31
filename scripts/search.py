from __future__ import annotations

from dataclasses import dataclass

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
    absolute_path: str = ""
    page_start: int | None = None
    page_end: int | None = None


def _keyword_overlap_score(query: str, content: str) -> float:
    query_terms = {term for term in query.lower().split() if len(term) > 2}
    if not query_terms:
        return 0.0
    content_lower = content.lower()
    hits = sum(1 for term in query_terms if term in content_lower)
    return hits / len(query_terms)


def rerank(query: str, results: list[SearchResult], limit: int = 5) -> list[SearchResult]:
    for result in results:
        lexical_boost = _keyword_overlap_score(query, result.content)
        result.score = (result.score * 0.85) + (lexical_boost * 0.15)
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
