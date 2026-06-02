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

### Generate wiki draft

UI field: `Topic`

API:

```bash
curl -X POST -d "topic=Project Alpha" http://127.0.0.1:8765/api/wiki-generate
```

What it does:

- Searches indexed sources for the topic.
- Creates a cited draft under `wiki/drafts/`.
- Keeps the page marked as `review_status: draft`.

### Promote reviewed draft

UI fields: `Draft slug`, `Reviewer name`

API:

```bash
curl -X POST -d "draft=project-alpha&reviewer=Vasu" http://127.0.0.1:8765/api/wiki-promote
```

What it does:

- Moves a reviewed draft from `wiki/drafts/` into `wiki/`.
- Marks the page as reviewed.
- Records the reviewer.
- Refuses accidental overwrites by default.

## AI-native operating loop

1. Add or edit source files in `vault/`.
2. Run `Ingest vault`.
3. Run `Build graph`.
4. Use Search to inspect retrieved chunks.
5. Use Ask for source-grounded answers.
6. Generate wiki drafts for stable topics.
7. Review and promote drafts when they are trustworthy.
8. Use Sources, Wiki, and Graph views to verify provenance.

## Activity history

The web UI stores recent Ask history and operation results in:

```text
data/web_activity.sqlite
```

This is local product memory for the operator cockpit. It survives server restarts, stays on the machine, and should be included with normal local backups if you want to preserve UI activity history.

## Safety

The web UI binds to localhost by default. For private network use, read `PRIVATE_ACCESS.md`.
