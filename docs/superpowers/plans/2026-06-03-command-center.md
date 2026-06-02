# Command Center v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested Command Center to the web UI that summarizes readiness, warnings, next actions, review queue, recent activity, and local memory paths.

**Architecture:** Keep this as a focused extension of the existing standard-library web app. Add one backend payload builder in `scripts/web.py`, render it in `render_dashboard()`, and test it through `tests/test_web.py`.

**Tech Stack:** Python stdlib HTTP server, SQLite-backed local activity history, `unittest`, existing Qdrant/graph/wiki helpers.

---

### Task 1: Command Center Payload

**Files:**
- Modify: `scripts/web.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing tests**

Add tests for `build_command_center_payload()` that expect:

```python
payload = build_command_center_payload(
    status={
        "qdrant_ready": True,
        "qdrant": "local",
        "vault_files": 2,
        "wiki_pages": 1,
        "graph_relationships": 4,
    },
    wiki_pages=[{"path": "drafts/project-alpha.md", "title": "Project Alpha", "review_status": "draft"}],
    chat_history=[{"question": "What is alpha?", "answer": "Alpha is local.", "mode": "fast", "confidence": "high"}],
    action_history=[{"name": "ingest", "status": "ok", "message": "Ingested 3 chunks."}],
)
assert payload["readiness"] == "warning"
assert "Review 1 wiki draft." in payload["next_actions"]
assert payload["review_queue"][0]["path"] == "drafts/project-alpha.md"
```

Also add a needs-attention test with Qdrant down and no vault files.

- [ ] **Step 2: Run focused test and confirm red**

Run:

```bash
uv run python -m unittest tests.test_web
```

Expected: fail because `build_command_center_payload` is not implemented.

- [ ] **Step 3: Implement payload builder**

Add `build_command_center_payload()` in `scripts/web.py`. It should accept optional `status`, `wiki_pages`, `chat_history`, and `action_history` arguments for testability, and use existing builders when omitted.

- [ ] **Step 4: Run focused test and confirm green**

Run:

```bash
uv run python -m unittest tests.test_web
```

Expected: all web tests pass.

### Task 2: Dashboard Rendering

**Files:**
- Modify: `scripts/web.py`
- Test: `tests/test_web.py`

- [ ] **Step 1: Write failing render test**

Update `test_render_dashboard_contains_product_sections` to assert:

```python
self.assertIn("Command Center", html)
self.assertIn("Next actions", html)
self.assertIn("Local memory map", html)
```

- [ ] **Step 2: Implement rendering**

Update `render_dashboard()` to accept `command_center`, build default payload when missing, and render a first-class section above Operations.

- [ ] **Step 3: Run focused tests**

Run:

```bash
uv run python -m unittest tests.test_web
```

Expected: all web tests pass.

### Task 3: Documentation and Smoke

**Files:**
- Modify: `PROJECT_PLAN.md`
- Modify: `WEB_OPERATIONS.md`

- [ ] **Step 1: Update docs**

Document Command Center v1 in Phase 6 progress and web operations.

- [ ] **Step 2: Run full smoke**

Run:

```bash
make smoke
```

Expected: compile, unit tests, doctor, status, audit, and retrieval evaluation all pass.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/specs/2026-06-03-command-center-design.md docs/superpowers/plans/2026-06-03-command-center.md PROJECT_PLAN.md WEB_OPERATIONS.md scripts/web.py tests/test_web.py
git commit -m "feat: add web command center"
```
