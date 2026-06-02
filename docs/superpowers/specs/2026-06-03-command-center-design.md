# Command Center v1 Design

## Goal

Make the web UI feel like a serious knowledge operating center, not just a collection of tools. The first screen should tell the user whether the system is healthy, what changed recently, what needs review, and what action is most useful next.

## Product Principle

Users love AI products when they feel powerful and trustworthy at the same time. Command Center v1 focuses on visible trust: readiness, source state, review queues, local memory locations, and concrete next actions.

## Scope

Command Center v1 adds a backend payload and dashboard section. It does not add background schedulers, backup execution, user accounts, or a React/Tailwind frontend. Those can come later after the local cockpit proves its workflow.

## Architecture

Add a `build_command_center_payload()` function in `scripts/web.py`. It will reuse existing project state readers instead of creating a new service layer: Qdrant health, vault/wiki file counts, graph relationship count, recent activity history, wiki drafts, and configured local data paths.

The payload returns:

- `readiness`: `healthy`, `warning`, or `needs_attention`
- `score`: integer from 0 to 100
- `next_actions`: short user-facing action recommendations
- `memory_map`: local paths for vault, wiki, metadata DB, graph DB, activity DB, and Qdrant data
- `review_queue`: draft wiki pages awaiting review
- `recent_activity`: recent Ask and operation history
- `warnings`: concrete production warnings

The dashboard renders this as the first major section after the status metrics.

## Data Flow

1. HTTP request reaches `render_dashboard()`.
2. The handler calls `build_command_center_payload()`.
3. The payload reads local state only.
4. HTML rendering shows readiness, warnings, next actions, review queue, and local memory map.

## Error Handling

The command center must degrade gracefully. If Qdrant or graph reads fail, it should show warnings and keep rendering. It should not crash the dashboard.

## Testing

Add unit tests in `tests/test_web.py` for:

- Healthy command center state with sources, graph facts, and activity.
- Warning state when Qdrant is down, graph facts are missing, drafts need review, or activity is empty.
- Dashboard renders the Command Center section.

Run focused web tests, then full `make smoke`.

## Success Criteria

- Web home screen has a Command Center section.
- Payload is deterministic and unit tested.
- User can see next actions and local memory paths without reading docs.
- Full smoke suite passes.
