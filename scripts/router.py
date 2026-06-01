from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from scripts.config import (
    OLLAMA_CHAT_MODEL,
    OLLAMA_HOST,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)
from scripts.search import SearchResult, format_citation

DEEP_QUERY_PATTERN = re.compile(
    r"\b(analy[sz]e|compare|synthesi[sz]e|explain in detail|pros and cons|"
    r"contradiction|implications|evaluate|deep dive|comprehensive)\b",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """You are a personal knowledge assistant with access to the user's private documents.
Answer ONLY using the provided context snippets.
If the context does not contain enough information, say exactly:
"No information found in your knowledge base."
Every factual claim must reference a source using [1], [2], etc.
Do not invent facts or sources."""

MIN_SOURCE_SCORE = 0.2
MIN_LEXICAL_COVERAGE = 0.25


@dataclass(frozen=True)
class SourceCoverage:
    supported: bool
    confidence: str
    lexical_coverage: float
    best_score: float


def _query_terms(query: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9]+", query.lower())
        if len(term) > 2
    }


def assess_source_coverage(query: str, sources: list[SearchResult]) -> SourceCoverage:
    if not sources:
        return SourceCoverage(False, "low", 0.0, 0.0)

    terms = _query_terms(query)
    combined = " ".join(source.content.lower() for source in sources)
    lexical_coverage = 1.0 if not terms else sum(1 for term in terms if term in combined) / len(terms)
    best_score = max(source.score for source in sources)
    best_lexical_score = max((source.lexical_score for source in sources), default=0.0)
    supported = (
        best_score >= MIN_SOURCE_SCORE
        and (lexical_coverage >= MIN_LEXICAL_COVERAGE or best_lexical_score >= MIN_LEXICAL_COVERAGE)
    )

    if supported and lexical_coverage >= 0.6:
        confidence = "high"
    elif supported:
        confidence = "medium"
    else:
        confidence = "low"

    return SourceCoverage(supported, confidence, lexical_coverage, best_score)


def _build_context(sources: list[SearchResult]) -> str:
    blocks: list[str] = []
    for index, source in enumerate(sources, start=1):
        citation = format_citation(source)
        blocks.append(f"[{index}] Source: {citation}\n{source.content}")
    return "\n\n---\n\n".join(blocks)


def choose_mode(query: str, force_deep: bool = False) -> str:
    if force_deep:
        return "deep"
    if len(query.split()) >= 18 or DEEP_QUERY_PATTERN.search(query):
        return "deep"
    return "fast"


def _chat_ollama(query: str, context: str) -> str:
    response = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json={
            "model": OLLAMA_CHAT_MODEL,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {query}",
                },
            ],
        },
        timeout=180.0,
    )
    if response.status_code == 404:
        raise RuntimeError(
            f"Chat model '{OLLAMA_CHAT_MODEL}' is not installed. "
            f"Run: ollama pull {OLLAMA_CHAT_MODEL}"
        )
    response.raise_for_status()
    payload = response.json()
    message = payload.get("message", {})
    return str(message.get("content", "")).strip()


def _chat_openrouter(query: str, context: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "Deep mode requires OPENROUTER_API_KEY in .env (or use --fast)."
        )

    response = httpx.post(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion: {query}",
                },
            ],
        },
        timeout=180.0,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", [])
    if not choices:
        raise RuntimeError("OpenRouter returned no choices.")
    return str(choices[0]["message"]["content"]).strip()


def synthesize_answer(
    query: str,
    sources: list[SearchResult],
    *,
    mode: str | None = None,
    force_deep: bool = False,
) -> tuple[str, str]:
    if not sources:
        return "No information found in your knowledge base.", "none"

    coverage = assess_source_coverage(query, sources)
    if not coverage.supported:
        return "No information found in your knowledge base.", "none"

    context = _build_context(sources)
    selected_mode = mode or choose_mode(query, force_deep=force_deep)

    if selected_mode == "deep":
        answer = _chat_openrouter(query, context)
    else:
        answer = _chat_ollama(query, context)

    return answer, selected_mode
