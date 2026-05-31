# Prerequisites

This project can run in two modes:

- Embedded local mode: Qdrant stores data under `data/qdrant`. This works without Docker.
- Server mode: Qdrant runs through Docker Compose. This requires Docker Desktop or another Docker runtime.

The default local metadata database is `data/metadata.sqlite`.

## Required

- macOS or Linux
- Python 3.12 or newer
- `uv`
- Ollama
- Ollama models:
  - `nomic-embed-text`
  - `llama3.2`

Install the Ollama models with:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
```

## Optional

- Docker Desktop, for Qdrant server mode:

```bash
docker compose up -d
```

- OpenRouter API key, for deep cloud reasoning:

```env
OPENROUTER_API_KEY=...
```

## Current Local Check

Checked on 2026-05-31:

- `uv` is installed.
- Python is installed.
- `.env` exists.
- Embedded Qdrant mode is working.
- Docker is not currently installed or not on `PATH`.
- Ollama models `nomic-embed-text`, `llama3.2`, and `llama3.2:1b` are installed.
- Unit tests pass with `uv run python -m unittest`.
- The full smoke workflow passes with `make smoke`.

## Validation Commands

```bash
uv run python -m unittest
uv run python main.py status
uv run python main.py audit
ollama list
```
