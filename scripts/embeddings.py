from __future__ import annotations

import httpx

from scripts.config import OLLAMA_EMBED_MODEL, OLLAMA_HOST


def embed_text(text: str) -> list[float]:
    response = httpx.post(
        f"{OLLAMA_HOST}/api/embeddings",
        json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=120.0,
    )
    response.raise_for_status()
    payload = response.json()
    embedding = payload.get("embedding")
    if not embedding:
        raise RuntimeError(f"Ollama returned no embedding for model {OLLAMA_EMBED_MODEL}")
    return embedding
