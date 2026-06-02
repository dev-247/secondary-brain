# Web Operations Guide

The web UI is a local operator cockpit for Second Brain. It is designed to keep core actions visible, source-backed, and safe.

## Start the UI

```bash
uv run python main.py web
```

Open:

```text
http://127.0.0.1:8765
```

## Available actions

### Ingest vault

UI button: `Run ingest`

API:

```bash
curl -X POST http://127.0.0.1:8765/api/ingest
```

What it does:

- Scans `vault/`.
- Indexes changed supported files.
- Skips unchanged files.
- Removes deleted files from the index.
- Reports chunks, skipped files, deleted files, and failures.

### Build graph

UI button: `Build graph`

API:

```bash
curl -X POST http://127.0.0.1:8765/api/graph-build
```

What it does:

- Reads indexed chunks from Qdrant.
- Extracts conservative graph facts.
- Stores entities, relationships, dependencies, and dated events in the local graph database.
- Preserves source path, chunk index, and evidence text.

## AI-native operating loop

1. Add or edit source files in `vault/`.
2. Run `Ingest vault`.
3. Run `Build graph`.
4. Use Search to inspect retrieved chunks.
5. Use Ask for source-grounded answers.
6. Use Sources, Wiki, and Graph views to verify provenance.

## Safety

The web UI binds to localhost by default. For private network use, read `PRIVATE_ACCESS.md`.
