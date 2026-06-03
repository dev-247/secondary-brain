# Second Brain MVP Showcase

This document is the demo guide for presenting Second Brain on GitHub, LinkedIn, or a portfolio.

## One-Line Pitch

Second Brain is a local-first AI memory system that searches private notes, answers with citations, and organizes knowledge into a personal wiki.

## 30-Second Demo Flow

1. Open the web UI at `http://127.0.0.1:8765`.
2. Show the Command Center readiness score and warnings.
3. Ask: `what is DI`.
4. Point out that the answer cites `DI.md`.
5. Open Search and show the ranked source chunks.
6. Show Sources/Wiki to prove the answer comes from local files.

## What To Emphasize

- It runs locally.
- It answers from your own knowledge, not generic web content.
- It cites sources.
- It has a command center for system readiness.
- It has the start of long-term AI memory: wiki drafts, graph memory, and activity history.

## Demo Script

```text
I built a local-first Second Brain for personal knowledge.

I can drop notes into a vault, run ingest, and then ask questions in a browser UI.
The answer is not just generated text: it is grounded in local files and shows citations.

For example, this note explains Dependency Injection in Flutter.
When I ask "what is DI", the system retrieves DI.md, answers from it, and cites the exact source chunk.

The goal is a private AI memory layer: raw files as source of truth, retrieval for accuracy,
wiki pages for long-term organization, graph memory for relationships, and optional cloud reasoning only when needed.
```

## MVP Strengths

- Useful for real personal notes today.
- Demonstrates retrieval, citations, local storage, and AI answer synthesis.
- Has tests and smoke evaluation, so it is more than a UI mockup.
- Strong architecture story for AI memory systems.

## Honest Limitations

- UI is still a lightweight Python web app, not a full React/shadcn product.
- Backup/restore is not yet complete.
- Graph extraction is conservative.
- Real-world evaluation needs more user notes.
- Public deployment/security review is still future work.

## Next Showcase Milestones

1. Backup and restore flow.
2. Graph-assisted Ask answers.
3. More polished browser UI.
4. Import/export tools.
5. Better demo dataset and screenshots.

