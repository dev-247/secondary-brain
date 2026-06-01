# Second Brain Production Project Plan

Last observed: 2026-05-31

## Product Direction

Build a production-grade, local-first hybrid second brain.

The winning architecture is not only RAG, only wiki generation, or only graph memory. It is a layered system:

```text
Raw files = source of truth
RAG = accurate retrieval and citations
LLM wiki = organized long-term memory
Graph layer = relationships, contradictions, timelines, and multi-hop insight
Local LLM = private everyday assistant
Cloud LLM = optional deep reasoning fallback
```

This keeps the system private and inspectable while still allowing high-quality reasoning when the user explicitly chooses it.

## Current State

This project is in an early working-prototype phase. The core local-first command-line path exists: files can be discovered from `vault/`, parsed, chunked, embedded, indexed into Qdrant, searched with dense plus sparse retrieval, and synthesized through either local Ollama or OpenRouter.

The repository was initialized on 2026-05-31 so future work can be tracked with commits. There is no older commit history before that date.

## Prerequisite Status

Checked on 2026-05-31:

| Prerequisite | Status | Notes |
| --- | --- | --- |
| `uv` | Installed | `uv 0.11.17` |
| Python | Installed | `Python 3.14.5`; project requires `>=3.12` |
| `.env` | Present | Local secrets/config file exists |
| Qdrant | Ready | Embedded local mode works at `data/qdrant` |
| Docker | Missing | `docker` command is not installed or not on `PATH`; not blocking embedded local mode |
| Ollama CLI | Installed | Client is available |
| Ollama models | Installed | `llama3.2`, `llama3.2:1b`, and `nomic-embed-text` are present |
| OpenRouter key | Optional | Required only for deep cloud reasoning |
| Tests | Passing | `uv run python -m unittest` passes 9 tests |

Remaining installation work:

- Install Docker Desktop only if we want Qdrant in server/container mode.
- Keep Ollama running when using ingestion, search, or local chat.
- Add an OpenRouter API key only if deep mode should call cloud LLMs.

## Completed

- Stage 1 infrastructure:
  - `docker-compose.yml` defines Qdrant on ports 6333 and 6334.
  - `vault/` and `wiki/` directories exist.
  - Qdrant can run in Docker server mode or embedded local mode.

- Stage 2 ingestion:
  - `scripts/ingest.py` discovers supported files in the vault.
  - Markdown and text files are read directly.
  - PDF/image/docx extraction is routed through Docling.
  - Chunks are stored with filename, path, heading, timestamp, and content payloads.

- Stage 3 retrieval:
  - `scripts/search.py` performs dense vector and sparse BM25 prefetch against Qdrant.
  - Results are fused with reciprocal rank fusion.
  - A simple lexical boost reranks returned chunks.

- Stage 4 intelligence routing:
  - `scripts/router.py` routes short/simple queries to local Ollama.
  - Longer or analytical queries route to OpenRouter unless fast mode is forced.
  - Prompt rules require answers to use retrieved context and cite sources.

- Stage 5 CLI:
  - `main.py` provides `status`, `ingest`, `ask`, `audit`, and `chat` commands.
  - Empty retrieval returns "No information found in your knowledge base."

- Audit:
  - `scripts/audit.py` reports indexed chunks, wiki file count, and stale wiki files.

## Gaps

- Project management:
  - Git, roadmap, development workflow, and release checklist now exist.
  - A changelog is still optional future polish.

- Validation:
  - Automated tests and smoke retrieval fixtures exist.
  - Retrieval quality evaluation is still small and should expand in Phase 2.

- Product scope:
  - The spec mentions access from anywhere in the research reference, but the current implementation is CLI-only.
  - There is no browser/PWA/mobile interface yet.
  - There is no authentication, remote-access setup, or private-network deployment guide.

- Data layer:
  - SQLite source metadata, index versioning, stale reingestion, and deleted-file cleanup now exist.
  - There is no deduplication across files.

- Retrieval quality:
  - Reranking is currently a simple keyword overlap heuristic.
  - Citations support file, heading, chunk, and page metadata when page markers are available.
  - There is no confidence scoring or source coverage summary.

- Wiki/self-improvement:
  - `wiki/` is present but no generation workflow writes summaries or articles.
  - Contradiction detection is listed in the spec but not implemented.
  - Topic suggestions are static and not based on vault analysis.

- Operations:
  - Ollama model availability is checked only when a request fails.
  - There is no backup/sync guidance in runnable form.
  - Docker health depends on the Qdrant image containing `curl`, which may be brittle.

## Production Phases

### Phase 0: Foundation and Baseline

Target: 1-2 days

- Initialize git and commit the baseline. Done.
- Keep deterministic unit tests passing. Done.
- Add a smoke test vault with known questions and expected source files. Done.
- Document required local services and model pulls. Done.
- Add a repeatable `make` or script-based developer workflow. Done.
- Define a release checklist for each phase. Done.

Exit criteria:

- Fresh clone setup is documented.
- Tests pass locally.
- A smoke ingest/search test can be run repeatedly.
- Baseline is committed.

### Phase 1: Reliable Ingestion

Target: 3-5 days

- Add document fingerprints and skip unchanged files. Done.
- Add delete/reindex behavior for removed or changed files. Done.
- Store canonical metadata in SQLite. Done.
- Improve citations for PDFs with page or section anchors where Docling exposes them. Done for page-aware citation plumbing; deeper Docling page extraction can be expanded with real PDF fixtures.
- Track parse errors without stopping the entire ingest run. Done.
- Record source MIME type, size, modified time, hash, parser version, and index version. Done.

Exit criteria:

- Re-running ingest does not duplicate unchanged content. Done.
- Changed and deleted files are reflected in the index. Done.
- Every indexed chunk has durable source metadata. Done.
- Failed files appear in a readable ingest report. Done.

Phase 1 review on 2026-05-31:

- `make smoke` passes with 28 tests.
- The repo is clean.
- The real local audit reports 3 indexed chunks.
- Remaining ingestion polish is deduplication across files and deeper real-PDF page extraction, both deferred because Phase 2 retrieval quality work is now more valuable.

### Phase 2: Retrieval Quality and Evaluation

Target: 3-5 days

- Build a small evaluation set of real user questions. Done: 10 fixture-backed evaluation questions exist.
- Measure recall of expected source chunks. Done: current deterministic benchmark reports recall@k.
- Replace keyword-overlap reranking with a stronger local or API reranker. Done for this phase: reranking is now pluggable with weighted lexical and lexical-only strategies; heavier local/API rerankers remain optional future work.
- Add retrieval diagnostics to show ranking details. Done for this phase: result rank, final score, fused score, lexical score, citation, chunk, heading, path, and preview are available; separate dense/sparse prefetch rankings remain future polish.
- Add commands for `eval` and `search --debug`. Done.
- Track retrieval quality before and after ranking changes. Done: latest eval JSON report is written to `reports/retrieval-eval-latest.json`.

Exit criteria:

- At least 10 evaluation questions exist. Done.
- The system reports whether expected sources were retrieved. Done.
- Retrieval changes are measured instead of guessed. Done: eval reports capture recall and per-question ranks.

Phase 2 review on 2026-05-31:

- `make smoke` passes with 28 tests.
- Retrieval evaluation passes 10/10 fixture-backed questions.
- Current recall@k is 100% on the deterministic fixture benchmark.
- Search diagnostics show rank, final score, fused score, lexical score, path, heading, chunk, citation, and preview.
- Remaining retrieval polish is deeper dense/sparse prefetch breakdown and optional model/API rerankers, both deferred until real-user evaluation data justifies them.

### Phase 3: Answer Quality and Trust

Target: 3-5 days

- Strengthen prompt templates for grounded answers. Done for current CLI flow; deeper prompt tuning is deferred until real answer transcripts exist.
- Add source coverage checks before synthesis. Done.
- Add confidence labels based on retrieval strength and source agreement. Done.
- Make abstention behavior consistent. Done.
- Add answer tests with mocked retrieval and mocked LLM responses. Done.

Exit criteria:

- The system refuses weakly supported answers. Done.
- Every factual answer includes citations. Done.
- Local and cloud modes share the same trust rules. Done.

Phase 3 review on 2026-06-01:

- `make smoke` passes with 35 tests.
- Weak source coverage is refused before local or cloud LLM calls.
- Answers carry low/medium/high confidence labels.
- Abstention is normalized to one message.
- Uncited generated answers are rejected.
- Local and cloud model outputs pass through the same trust gate.

### Phase 4: LLM Wiki Memory

Target: 1 week

- Add a command to generate source summaries into `wiki/`. Done for this phase: deterministic cited draft generation is available with `wiki-generate`.
- Add stale-topic refresh suggestions based on indexed documents. Done for audit: stale wiki pages are matched with newer indexed sources when their topic tokens overlap.
- Add contradiction candidates using retrieved claims and cited excerpts. Done for audit: indexed chunks are scanned for related notes with opposite signal words and surfaced as review candidates.
- Store generated wiki pages with citation blocks and review status. Done for this phase: generated pages include source citations, draft review metadata, and safe promotion to reviewed pages.
- Separate human-approved wiki pages from draft AI pages. Done for this phase: generated pages are written under `wiki/drafts/`, audit reports draft versus reviewed pages separately, and `wiki-promote` moves reviewed drafts into `wiki/`.

Exit criteria:

- The wiki becomes a browsable organized memory layer.
- Generated pages cite original sources.
- Draft pages are clearly marked as generated until reviewed, and audit lists drafts that still need human review.
- Reviewed drafts can be promoted without silently overwriting existing wiki pages.
- Stale wiki pages can be linked back to newer source notes that may refresh them.
- Possible contradictions are shown as review candidates with source paths, signals, and shared topic terms.

Phase 4 review on 2026-06-01:

- `make smoke` passes with 43 tests.
- `wiki-generate` creates cited AI draft pages under `wiki/drafts/`.
- `wiki-promote` moves reviewed drafts into `wiki/`, records the reviewer, and refuses accidental overwrites by default.
- Audit separates draft and reviewed wiki pages, lists drafts awaiting review, suggests stale-topic refresh sources, and flags conservative contradiction candidates.
- Remaining gap: contradiction and refresh detection are intentionally heuristic; stronger semantic claim extraction belongs in Phase 5 graph memory.

### Phase 5: Graph Memory and Higher-Level Insight

Target: 1-2 weeks

- Extract entities, topics, dates, projects, people, and relationships. In progress: deterministic extraction handles explicit project/topic/date mentions and simple `uses` / `depends on` relationships.
- Build a local graph store or SQLite-backed graph tables. Done for foundation: SQLite graph tables store normalized entities and source-backed relationships.
- Add graph-assisted questions such as "how are these ideas connected?" In progress: `graph <entity>` shows inbound and outbound relationships with source evidence.
- Add contradiction, timeline, and dependency discovery.

Exit criteria:

- The graph layer improves relationship and multi-hop queries.
- Graph facts link back to source chunks.

Phase 5 progress on 2026-06-01:

- `make smoke` passes with 49 tests.
- Added a local SQLite graph store with entity de-duplication by normalized name.
- Added source-backed relationships that preserve source path, chunk index, and evidence text.
- Added `graph-build` to scan indexed chunks, extract conservative graph candidates, and store them locally.
- Added `graph <entity>` to inspect graph connections for an entity with evidence and source chunks.
- Wrong or low-confidence extracted relationships can be reviewed.

### Phase 6: Product Interface and Access Anywhere

Target: 1-2 weeks

- Add a small API service around search and synthesis.
- Build a browser-first UI.
- Add private access guidance for Tailscale or equivalent.
- Add authentication before any non-local exposure.
- Add source viewer, chat history, wiki browser, and ingestion status.
- Keep the first UI dense and useful rather than marketing-like.

Exit criteria:

- A user can ingest, search, ask, inspect citations, and browse wiki pages from a web UI.
- Remote access is private by default.
- No service is exposed publicly without authentication.

### Phase 7: Production Operations

Target: ongoing

- Add backups for vault, metadata, Qdrant data, and wiki.
- Add structured logs and health checks.
- Add import/export tools.
- Add package/install instructions.
- Add security review for cloud calls and remote access.

Exit criteria:

- The system can be restored from backup.
- Common failures have visible diagnostics.
- Setup, upgrade, and recovery are documented.

## Recommended Next Work

The next best engineering move is Phase 0: stabilize the prototype. This makes the existing work trustworthy before expanding into UI, sync, wiki memory, or graph reasoning.

Immediate checklist:

- Run `make smoke`.
- Expand smoke retrieval from 4 fixture questions to 10 representative questions.
- Add a smoke ingest/search check against a user-selected real vault subset.
- Then improve ingestion freshness and retrieval diagnostics.
