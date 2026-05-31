# Development Workflow

## Daily Commands

Run all local checks:

```bash
make smoke
```

Run unit tests:

```bash
make test
```

Check local prerequisites:

```bash
make doctor
```

Check project status:

```bash
make status
```

Run the audit report:

```bash
make audit
```

Ingest the vault:

```bash
make ingest
```

Start interactive chat:

```bash
make chat
```

## Phase 0 Goal

Phase 0 exists to make the prototype trustworthy before adding bigger features.

The project should always have:

- a clean git baseline,
- repeatable local checks,
- clear prerequisite documentation,
- a smoke command,
- and a release checklist.

## Local Modes

Embedded Qdrant mode works without Docker and stores data under `data/qdrant`.

Docker Qdrant mode is optional. Use it when Docker Desktop is installed:

```bash
docker compose up -d
```
