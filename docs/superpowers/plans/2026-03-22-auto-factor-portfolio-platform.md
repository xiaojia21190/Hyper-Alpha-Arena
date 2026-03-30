# Auto Factor Portfolio Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end automatic pipeline that generates multi-factor portfolios, runs staged backtests, selects the strongest portfolio, and deploys it into paper trading first and live trading with explicit risk gates.

**Architecture:** Reuse the existing `FactorResearchService` as the orchestration backbone, extend it from single-factor ranking to portfolio construction and ranking, persist run outputs for reproducibility, and bridge winning portfolios into the existing Program Trader binding/execution runtime. Keep deployment conservative: auto-promote to paper only, manual approval for live.

**Tech Stack:** FastAPI, SQLAlchemy ORM + migration scripts, existing `backend/services/factor_research_service.py`, existing `backend/backtest/*`, existing Program Trader stack (`backend/routes/program_routes.py`, `backend/services/program_execution_service.py`), React + Vite, existing `frontend/app/components/factor/FactorLibrary.tsx`, `uv`, `pytest`, `pnpm build`

---

## Scope Check

This plan intentionally combines three dependent requirements into one closed loop:

`Auto research -> Portfolio generation -> Backtest ranking -> Winner persistence -> Paper deployment -> Live promotion gate`

Non-goals for this iteration:

- No new third-party dependencies.
- No replacement of existing Program Trader runtime.
- No fully automatic live deployment without a manual gate.

## Execution Status (2026-03-30)

Completed in code:

- Task 1 (persistence baseline): completed.
- Task 2 (portfolio candidate construction): completed.
- Task 3 (research orchestration portfolio extension): completed.
- Task 4 (portfolio -> Program Trader deployment bridge): completed.
- Task 5 (portfolio query/deploy APIs + router registration): completed.
- Task 6 (auto paper promotion wiring with env flags): completed.
- Task 7 (frontend API integration + FactorLibrary deployment panel): completed.

Verification snapshot:

- Targeted backend tests for new/changed scope: PASS (`37 passed`).
- Targeted lint (`ruff check`) on backend project: PASS.
- Frontend build (`pnpm build`): PASS.
- Full backend suite (`uv run pytest -q`): PASS (`52 passed`).
- Backend import smoke (`uv run python -c "import main; print('import-ok')"`) : PASS.
- Global backend lint gate (`cd backend && uv run ruff check .`): PASS.
- Added regression lock for compatibility fallback when `pandas_ta` import is unavailable: `backend/tests/services/test_technical_indicators.py`.
- Added regression lock for expression-engine degradation path when TA functions are unavailable:
  - `backend/tests/services/test_factor_expression_engine.py`
- Added operator checklist and smoke script for go-live rehearsal:
  - `docs/superpowers/plans/2026-03-22-factor-portfolio-go-live-checklist.md`
  - `backend/scripts/factor_portfolio_smoke.py`
- Lightweight end-to-end smoke run result (local): PASS (`--top-n-symbols 3 --lookback-days 7 --prescreen-limit 2`).

Current branch note:

- This plan is implemented on the current branch and remains the main product surface.
- Some later UI reshaping moved beyond `FactorLibrary.tsx` into dedicated workspace pages, but the portfolio platform behavior remains present.
- The checkbox task list below was not backfilled after implementation. Treat this status section and the current codebase as authoritative.

## File Structure

### New files

- `backend/database/migrations/create_factor_portfolio_tables.py`
  - Create persistence tables for research runs, portfolio candidates, and deployment records.
- `backend/services/factor_portfolio_service.py`
  - Construct weighted portfolio candidates from factor candidates, rank by objective and robustness.
- `backend/services/factor_portfolio_deployment_service.py`
  - Convert selected portfolio into Program Trader code and create/update program bindings.
- `backend/api/factor_portfolio_routes.py`
  - Expose list/detail/deploy-paper/deploy-live endpoints.
- `backend/tests/services/test_factor_portfolio_service.py`
  - Unit tests for portfolio candidate generation and ranking.
- `backend/tests/services/test_factor_portfolio_deployment_service.py`
  - Unit tests for deployment adaptation to Program Trader.
- `backend/tests/api/test_factor_portfolio_routes.py`
  - Route tests for retrieval and deployment controls.

### Modified files

- `backend/services/factor_research_service.py`
  - Extend orchestration to include portfolio build/backtest/ranking and persistent outputs.
- `backend/services/startup.py`
  - Wire auto-paper-promotion behavior and scheduler settings.
- `backend/config/settings.py`
  - Add portfolio/deployment env flags and defaults.
- `backend/api/factor_research_routes.py`
  - Return portfolio-level summary in status payload.
- `backend/main.py`
  - Register new factor portfolio router.
- `backend/database/models.py`
  - Add ORM models for new persistence tables.
- `frontend/app/lib/api.ts`
  - Add types and client calls for portfolio run/deploy APIs.
- `frontend/app/components/factor/FactorLibrary.tsx`
  - Display portfolio leaderboard and deploy actions.
- `backend/tests/services/test_factor_research_service.py`
  - Expand assertions to portfolio-level outputs.
- `backend/tests/api/test_factor_research_routes.py`
  - Expand route assertions for portfolio payload fields.

---

### Task 1: Define Portfolio Domain Contracts And Persistence Baseline

**Files:**
- Create: `backend/database/migrations/create_factor_portfolio_tables.py`
- Modify: `backend/database/models.py`
- Create: `backend/tests/services/test_factor_portfolio_service.py`

- [ ] **Step 1: Write failing tests for persistence contract assumptions**

Add tests that assert:

- a research run record stores run config and summary status.
- portfolio rows belong to a run and preserve component weights.
- deployment rows track `mode` (`paper` or `live`) and `status`.

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_service.py -v`

Expected: `FAIL` because portfolio models/tables do not exist.

- [ ] **Step 3: Implement migration + ORM models minimally**

Add:

- `FactorResearchRun`
- `FactorPortfolioCandidate`
- `FactorPortfolioDeployment`

Use JSON text columns for config/result snapshots to reuse current model style.

- [ ] **Step 4: Re-run targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit persistence baseline**

```bash
git add backend/database/models.py backend/database/migrations/create_factor_portfolio_tables.py backend/tests/services/test_factor_portfolio_service.py
git commit -m "feat: add factor portfolio persistence models"
```

### Task 2: Build Portfolio Candidate Construction Layer

**Files:**
- Create: `backend/services/factor_portfolio_service.py`
- Create: `backend/tests/services/test_factor_portfolio_service.py`

- [ ] **Step 1: Add failing unit tests for portfolio construction methods**

Cover at least:

- `equal_weight_top_n`
- `score_weighted_top_n`
- `category_balanced_weighted`

Assertions:

- weights sum to 1.0.
- component list is deterministic.
- low-quality factor rows are excluded.

- [ ] **Step 2: Run tests and confirm failure**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_service.py -v`

Expected: `FAIL` because service functions do not exist.

- [ ] **Step 3: Implement minimal construction + ranking helpers**

Implement:

- `build_portfolio_candidates(factor_rows, top_n)`
- `score_portfolio_candidate(candidate, objective)`
- `rank_portfolio_candidates(candidates)`
- `pick_recommended_portfolio(candidates)`

- [ ] **Step 4: Re-run tests**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit portfolio service baseline**

```bash
git add backend/services/factor_portfolio_service.py backend/tests/services/test_factor_portfolio_service.py
git commit -m "feat: add factor portfolio candidate builder"
```

### Task 3: Extend Research Orchestration From Single-Factor To Portfolio-Level

**Files:**
- Modify: `backend/services/factor_research_service.py`
- Modify: `backend/tests/services/test_factor_research_service.py`
- Modify: `backend/tests/services/test_factor_research_integration.py`

- [ ] **Step 1: Add failing tests for portfolio outputs**

Require `run_research()` to return:

- `portfolio_candidates`
- `portfolio_ranked_results`
- `top_portfolio`

Keep compatibility fields:

- `ranked_results`
- `top_factor`

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_research_integration.py -v`

Expected: `FAIL` on missing portfolio fields.

- [ ] **Step 3: Integrate `factor_portfolio_service` into research pipeline**

Flow:

1. existing factor prescreen
2. staged factor backtest
3. build portfolio candidates from top factor rows
4. staged portfolio backtest
5. rank and select `top_portfolio`
6. persist run + portfolio candidates

- [ ] **Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_research_integration.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit orchestration upgrade**

```bash
git add backend/services/factor_research_service.py backend/tests/services/test_factor_research_service.py backend/tests/services/test_factor_research_integration.py
git commit -m "feat: extend factor research to portfolio-level ranking"
```

### Task 4: Add Program Trader Deployment Bridge For Winning Portfolio

**Files:**
- Create: `backend/services/factor_portfolio_deployment_service.py`
- Create: `backend/tests/services/test_factor_portfolio_deployment_service.py`
- Modify: `backend/database/models.py`

- [ ] **Step 1: Add failing tests for deployment adapter behavior**

Cover:

- generate program code from portfolio weights.
- create or update `TradingProgram`.
- create or update `AccountProgramBinding`.
- create deployment record with `paper` or `live`.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_deployment_service.py -v`

Expected: `FAIL` because adapter service does not exist.

- [ ] **Step 3: Implement deployment service using existing Program Trader entities**

Reuse:

- `TradingProgram`
- `AccountProgramBinding`
- existing trigger interval and pool bindings policy

Do not duplicate execution logic already in `program_execution_service`.

- [ ] **Step 4: Re-run focused tests**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_deployment_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit deployment bridge**

```bash
git add backend/services/factor_portfolio_deployment_service.py backend/tests/services/test_factor_portfolio_deployment_service.py backend/database/models.py
git commit -m "feat: add portfolio-to-program deployment bridge"
```

### Task 5: Add Portfolio APIs (Query + Deploy Controls)

**Files:**
- Create: `backend/api/factor_portfolio_routes.py`
- Modify: `backend/main.py`
- Modify: `backend/api/factor_research_routes.py`
- Create: `backend/tests/api/test_factor_portfolio_routes.py`
- Modify: `backend/tests/api/test_factor_research_routes.py`

- [ ] **Step 1: Write failing API tests**

Cover:

- get latest successful run with portfolio leaderboard.
- list deployment records.
- deploy selected portfolio to paper account.
- reject deploy-live without explicit `confirm_live=true`.

- [ ] **Step 2: Run API tests and verify failure**

Run: `cd backend && uv run pytest tests/api/test_factor_portfolio_routes.py tests/api/test_factor_research_routes.py -v`

Expected: `FAIL` because routes are not wired.

- [ ] **Step 3: Implement routes and register router**

Add endpoints under `/api/factor-portfolios`:

- `GET /latest`
- `GET /runs/{run_id}`
- `POST /{portfolio_id}/deploy-paper`
- `POST /{portfolio_id}/deploy-live`
- `GET /deployments`

- [ ] **Step 4: Re-run API tests**

Run: `cd backend && uv run pytest tests/api/test_factor_portfolio_routes.py tests/api/test_factor_research_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit API layer**

```bash
git add backend/api/factor_portfolio_routes.py backend/main.py backend/api/factor_research_routes.py backend/tests/api/test_factor_portfolio_routes.py backend/tests/api/test_factor_research_routes.py
git commit -m "feat: expose factor portfolio query and deployment APIs"
```

### Task 6: Wire Scheduler To Auto-Deploy Winner To Paper (Not Live)

**Files:**
- Modify: `backend/services/factor_research_service.py`
- Modify: `backend/services/startup.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/tests/services/test_factor_research_integration.py`

- [ ] **Step 1: Add failing integration test for auto-paper-promotion**

Scenario:

- research run succeeds with top portfolio.
- `FACTOR_RESEARCH_AUTO_PROMOTE_PAPER=true`.
- deployment service is called once for `paper`.

- [ ] **Step 2: Run test and verify failure**

Run: `cd backend && uv run pytest tests/services/test_factor_research_integration.py -v`

Expected: `FAIL` on missing auto-promotion behavior.

- [ ] **Step 3: Implement guarded auto-promotion**

Add settings:

- `FACTOR_RESEARCH_AUTO_PROMOTE_PAPER`
- `FACTOR_RESEARCH_PAPER_ACCOUNT_ID`
- `FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM` (default true)

Live deployment remains manual route only.

- [ ] **Step 4: Re-run integration test**

Run: `cd backend && uv run pytest tests/services/test_factor_research_integration.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit scheduler/deployment wiring**

```bash
git add backend/services/factor_research_service.py backend/services/startup.py backend/config/settings.py backend/tests/services/test_factor_research_integration.py
git commit -m "feat: auto-promote winning portfolio to paper trading"
```

### Task 7: Frontend Integration For Portfolio Leaderboard And Deploy Actions

**Files:**
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/components/factor/FactorLibrary.tsx`

- [ ] **Step 1: Add API types and calls for new endpoints**

Include:

- `FactorPortfolioCandidate`
- `FactorPortfolioDeployment`
- `getLatestFactorPortfolioRun()`
- `deployFactorPortfolioPaper()`
- `deployFactorPortfolioLive()`

- [ ] **Step 2: Add UI section in FactorLibrary**

Show:

- top 3 portfolio leaderboard
- recommended portfolio card
- deploy-paper button
- deploy-live button with confirm text

- [ ] **Step 3: Build frontend and fix typing issues**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [ ] **Step 4: Commit frontend integration**

```bash
git add frontend/app/lib/api.ts frontend/app/components/factor/FactorLibrary.tsx
git commit -m "feat: add portfolio leaderboard and deploy actions in factor workspace"
```

### Task 8: Regression, Compatibility, And Safety Verification

**Files:**
- No new files unless fixes are required

- [ ] **Step 1: Run backend targeted suite for changed areas**

Run:

`cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -v`

Expected: `PASS`

- [ ] **Step 2: Run backend lint/static checks**

Run: `cd backend && uv run ruff check .`

Expected: no new lint errors.

- [ ] **Step 3: Run full backend test suite**

Run: `cd backend && uv run pytest -v`

Expected: `PASS` or documented pre-existing unrelated failures.

- [ ] **Step 4: Run frontend build gate**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [ ] **Step 5: Smoke-check app import/runtime**

Run: `cd backend && uv run python -c "import main; print('import-ok')"`

Expected: `import-ok`

- [ ] **Step 6: Commit verification notes if fixes were required**

```bash
git add -A
git commit -m "chore: finalize auto factor portfolio platform verification"
```

---

## Acceptance Criteria

- Automated research produces portfolio candidates and a deterministic `top_portfolio`.
- Research results persist in database and survive service restart.
- Top portfolio can be deployed to paper trading via API and UI.
- Live deployment requires explicit confirmation and never auto-runs.
- Existing `top_factor` and current factor research UI remain backward compatible.
- Program Trader execution path remains unchanged and is reused for runtime orders.

## Risks And Mitigations

- Risk: portfolio overfitting to one lookback window.
  - Mitigation: staged backtests and minimum robustness fields (`trade_count`, `drawdown`, `sharpe`) in ranking.
- Risk: accidental live deployment.
  - Mitigation: explicit `confirm_live=true` gate and env default deny.
- Risk: environment-specific failures (`pandas_ta` on Windows/Python 3.13).
  - Mitigation: keep test matrix focused, run Linux/Python 3.12 CI gate before release.
- Risk: breaking existing factor research responses.
  - Mitigation: additive schema changes only, preserve `top_factor` and `ranked_results`.

## Verification Steps

- Backend unit + API tests for all new portfolio and deployment services.
- Integration test proving automatic paper promotion path.
- Frontend build success and manual deploy button smoke test.
- Runtime smoke check for app import and route registration.

## Delivery Sequence

1. Persistence and portfolio builder.
2. Research orchestration upgrade.
3. Deployment bridge and APIs.
4. Scheduler auto-paper-promotion.
5. Frontend integration.
6. Regression and rollout checks.
