from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _path(name: str, default: str) -> Path:
    return (ROOT / os.getenv(name, default)).resolve()


QDRANT_MODE = os.getenv("QDRANT_MODE", "auto")  # auto | server | local
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "second_brain")
QDRANT_PATH = _path("QDRANT_PATH", "data/qdrant")
METADATA_DB_PATH = _path("METADATA_DB_PATH", "data/metadata.sqlite")
GRAPH_DB_PATH = _path("GRAPH_DB_PATH", "data/graph.sqlite")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
EMBED_DIMENSION = int(os.getenv("EMBED_DIMENSION", "768"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")

VAULT_DIR = _path("VAULT_DIR", "vault")
WIKI_DIR = _path("WIKI_DIR", "wiki")

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"}
