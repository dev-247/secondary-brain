# Release Checklist

Use this checklist at the end of every production phase.

## Required

- `make smoke` passes.
- Retrieval smoke cases pass.
- `git status --short` shows only intentional changes.
- New behavior has tests or a documented reason tests are not practical.
- User-facing commands are documented.
- Any new optional dependency is listed in `PREREQUISITES.md`.
- Any new secret or environment variable is listed in `.env.example`.
- The phase section in `PROJECT_PLAN.md` is updated.

## Phase Review

Before committing a phase:

1. Confirm what changed.
2. Confirm what was validated.
3. Confirm what remains.
4. Commit with a clear message.

## Current Baseline

Baseline commit:

```text
9c7aaec chore: establish second brain baseline
```
