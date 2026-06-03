# Second Brain

A local-first AI knowledge assistant for private notes, research, and project memory.

Second Brain turns a local `vault/` folder into a searchable, source-cited knowledge system. It can ingest notes, search them semantically and lexically, answer questions with citations, draft wiki pages, and show system readiness in a local browser UI.

## Why It Exists

Most AI assistants forget context, hallucinate, or require uploading personal knowledge to a cloud product. Second Brain is designed around a different principle:

```text
Your files are the source of truth.
AI answers must cite those files.
Memory should be local, inspectable, and rebuildable.
```

## MVP Features

- Local vault ingestion for Markdown, text, PDFs, images, and docx files.
- Hybrid search using vector retrieval plus BM25-style sparse search.
- Source-grounded Ask flow with citations and confidence labels.
- Answer quality safeguards for weak sources, missing citations, and acronym definitions.
- AI wiki draft generation with human review/promotion flow.
- SQLite-backed graph memory for source-backed relationships and timelines.
- Local web UI with Command Center, Ask, Search, Sources, Wiki, and Operations.
- Private access guardrails for local/private-network use.
- Persistent local activity history for recent questions and operations.

## Current Demo

The MVP can answer questions from local knowledge.

Example:

```text
Question: what is DI

Answer: Dependency Injection in Flutter (GetIt + Injectable, Clean Architecture):
Flutter's get_it package provides a simple, fast service locator/DI container. [1]

Source: DI.md
```

## Quick Start

Install prerequisites from [PREREQUISITES.md](./PREREQUISITES.md), then run:

```bash
uv sync
make doctor
make ingest
make web
```

Open:

```text
http://127.0.0.1:8765
```

Put your knowledge files in:

```text
vault/
```

Then run ingestion again from the web UI or CLI:

```bash
make ingest
```

## Useful Commands

```bash
make smoke
make doctor
make ingest
make web
uv run python main.py search "your query" --debug
uv run python main.py ask "your question" --fast
uv run python main.py wiki-generate "topic"
uv run python main.py graph-build
```

## Architecture

```text
vault/ files
  -> parsing and chunking
  -> Qdrant hybrid index
  -> source metadata in SQLite
  -> Ask/Search with citations
  -> reviewed wiki and graph memory
  -> local browser Command Center
```

Core layers:

- `vault/`: raw source knowledge.
- `data/qdrant`: local hybrid retrieval index.
- `data/metadata.sqlite`: indexed source metadata.
- `data/graph.sqlite`: graph facts and source-backed relationships.
- `data/web_activity.sqlite`: recent web activity history.
- `wiki/`: reviewed and draft long-term memory pages.

## Validation

Current verified baseline:

```text
make smoke
73 tests passing
10/10 smoke retrieval cases
```

## Showcase Materials

- [MVP showcase guide](./docs/SHOWCASE_MVP.md)
- [LinkedIn, portfolio, and GitHub launch copy](./docs/SOCIAL_LAUNCH_COPY.md)

## Status

This is a strong local MVP, not yet a public production SaaS. It is ready to showcase as a privacy-first AI memory prototype and personal knowledge assistant.

Best current use cases:

- personal coding notes
- research notes
- founder/project memory
- document search
- source-cited Q&A
- early AI memory experiments

Next production steps are backup/restore, better onboarding, graph-assisted answers, a more polished frontend, and package/deployment flow.

## Privacy

Second Brain is local-first. The default web UI binds to localhost. Cloud reasoning is optional and only used when configured.

See [PRIVATE_ACCESS.md](./PRIVATE_ACCESS.md) before exposing the app beyond localhost.
