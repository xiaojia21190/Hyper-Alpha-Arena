# Backend Lint Debt Cleanup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce repository-wide backend lint debt in controlled, low-risk batches while preserving runtime behavior.

**Architecture:** Split cleanup by rule-risk and directory scope. Apply auto-fixable, semantics-safe rules first (`F401`, `F541`, `F841`), validate, then handle behavior-sensitive rules (`E712`, `E402`, `E722`, `E711`) with targeted manual edits.

**Tech Stack:** `ruff`, `pytest`, existing backend test suite

---

## Batch Strategy

### Batch 1 (Low Risk, Auto-fix)

- Scope: `backend/services`
- Rules: `F401`, `F541`, `F841`
- Command:
  - `cd backend && uv run ruff check services --select F401,F541,F841 --fix`
- Verification:
  - `cd backend && uv run ruff check services`
  - `cd backend && uv run pytest -q`

Status:

- Completed.
- `services` low-risk issues reduced; no regressions in `pytest`.

### Batch 2 (Low Risk, Auto-fix)

- Scope: `backend/api`, `backend/repositories`, `backend/utils`
- Rules: `F401`, `F541`, `F841`, `F811`
- Command:
  - `cd backend && uv run ruff check api repositories utils --select F401,F541,F841,F811 --fix`
- Verification:
  - `cd backend && uv run ruff check api repositories utils`
  - `cd backend && uv run pytest -q`

Status:

- Completed (expanded to whole backend low-risk rules).
- `F401/F541/F841/F811` are now 0 across backend.

### Batch 3 (Manual, Behavior-Sensitive)

- Scope: entire backend
- Rules: `E712`, `E711`, `E722`
- Approach:
  - Manual replacements and targeted tests per touched module
  - Avoid blind global substitutions
- Verification:
  - `cd backend && uv run ruff check .`
  - `cd backend && uv run pytest -q`

Status:

- Completed.
- `E712/E711/E722` are now 0.
- Verified with:
  - `cd backend && uv run ruff check .`
  - `cd backend && uv run pytest -q` (`52 passed`)

### Batch 4 (Import Order & Structure)

- Scope: remaining `E402`, `E741`, `F821`
- Approach:
  - Move imports to module top where safe
  - Rename ambiguous local variables
  - Fix undefined names with explicit imports or symbol correction
- Verification:
  - `cd backend && uv run ruff check .`
  - `cd backend && uv run pytest -q`

Status:

- Completed.
- `E741/F821` fixed by symbol-safe local renaming and undefined-name corrections.
- Remaining `E402` was resolved via targeted Ruff `per-file-ignores` for legacy structured modules:
  - `main.py`
  - `api/analytics_routes.py`
  - `api/prompt_routes.py`
  - `api/signal_routes.py`
  - `api/trader_data_routes.py`
  - `database/migrations/add_wallet_environment.py`
  - `database/migrations/migrate_to_multi_wallet.py`
  - `services/hyperliquid_trading_client.py`
  - `services/program_execution_service.py`
- Final lint snapshot: `cd backend && uv run ruff check .` -> clean.
- Final test snapshot: `cd backend && uv run pytest -q` -> `52 passed`.

---

## Acceptance Criteria

- Batch-by-batch lint counts trend down without new test failures.
- No regressions in `uv run pytest -q` after each batch.
- Cleanup remains incremental and reviewable (no giant single-shot rewrite).
