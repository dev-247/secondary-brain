from __future__ import annotations

import httpx
from qdrant_client import QdrantClient, models

from scripts.config import (
    EMBED_DIMENSION,
    QDRANT_COLLECTION,
    QDRANT_HOST,
    QDRANT_MODE,
    QDRANT_PATH,
    QDRANT_PORT,
)


def qdrant_url() -> str:
    return f"http://{QDRANT_HOST}:{QDRANT_PORT}"


def _server_healthy() -> bool:
    try:
        response = httpx.get(f"{qdrant_url()}/healthz", timeout=5.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def using_local_mode() -> bool:
    if QDRANT_MODE == "local":
        return True
    if QDRANT_MODE == "server":
        return False
    return not _server_healthy()


def qdrant_status_label() -> str:
    if using_local_mode():
        return f"local ({QDRANT_PATH})"
    return f"server ({qdrant_url()})"


def get_client() -> QdrantClient:
    if using_local_mode():
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(QDRANT_PATH))
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def check_qdrant_health() -> bool:
    if using_local_mode():
        return True
    return _server_healthy()


def ensure_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()
    collections = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION in collections:
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            "dense": models.VectorParams(
                size=EMBED_DIMENSION,
                distance=models.Distance.COSINE,
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
        },
    )
