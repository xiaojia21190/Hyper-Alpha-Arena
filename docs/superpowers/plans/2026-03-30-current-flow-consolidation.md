# Current Flow Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the already-validated factor product line into one canonical user flow and one canonical regression entrypoint without re-introducing a separate `Strategy / Confirm / Validate` product layer.

**Architecture:** Make one frontend route the canonical entry for the factor workflow, and let it expose `research -> deployments -> live gate` as stages inside the same surface. Keep old hashes as compatibility aliases only. On the backend/docs side, standardize one smoke/regression command around the existing factor portfolio smoke runner so the validated runtime can be re-checked without remembering multiple ad-hoc commands.

**Tech Stack:** React 18, TypeScript, Vite, FastAPI, Python 3.12, pytest, uv, pnpm

## Execution Status

- Status: implementation landed on the current branch; runtime smoke remains environment-blocked
- Commits:
  - `99d2707` `refactor: canonicalize factor pipeline entry`
  - `5e3ff5a` `refactor: split factor pipeline stages`
  - `7fb8ae5` `docs: standardize factor flow smoke verification`
  - `1994e46` `chore: track factor portfolio smoke script`
- Verified:
  - `cd frontend && pnpm build`
  - `cd backend && uv run pytest tests/scripts/test_factor_portfolio_smoke.py -q`
  - `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q`
  - `cd backend && uv run python -c "import main; print('import-ok')"`
- Blocked:
  - `cd backend && uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611`
  - Result: `ConnectionRefused` because no backend was listening on `localhost:5611`
- Residual low-risk notes:
  - empty hash does not auto-normalize to `#factor-pipeline?stage=research`
  - frontend build still emits the pre-existing Vite chunk-size / baseline-browser mapping warnings

---

## Scope Guard

This plan is intentionally narrow.

Do:

- merge the factor workflow into one first-class page/route
- reduce duplicate or dead factor UI surfaces
- keep legacy pages reachable only through compatibility aliases when needed
- standardize the smoke/regression path for the current factor runtime
- update docs to point to the new canonical flow

Do not:

- add a new visible `Strategy` layer
- redesign factor research algorithms
- widen scope into Binance / bot / Hyper AI cleanup unless a direct blocker appears
- fold unrelated dirty workspace files into these commits

## File Map

- Modify: `frontend/app/main.tsx`
  - introduce a canonical factor-flow route and keep old hashes as aliases
- Modify: `frontend/app/components/layout/Sidebar.tsx`
  - reduce top-level factor navigation to one primary entry and demote legacy surfaces
- Modify: `frontend/app/components/factor/FactorPipelineWorkspace.tsx`
  - convert the current three-view surface into one staged workflow container
- Create: `frontend/app/components/factor/FactorPipelinePage.tsx`
  - own stage parsing, hash/query compatibility, and top-level factor-flow shell
- Create: `frontend/app/components/factor/pipeline/ResearchStage.tsx`
  - extract research-stage rendering from the oversized workspace file
- Create: `frontend/app/components/factor/pipeline/DeploymentsStage.tsx`
  - extract deployment-stage rendering
- Create: `frontend/app/components/factor/pipeline/LiveGateStage.tsx`
  - extract live-gate rendering
- Optional Create: `frontend/app/components/factor/pipeline/useFactorPipelineData.ts`
  - move polling/data-loading logic out of the page component if the split otherwise keeps `FactorPipelineWorkspace.tsx` too large
- Delete: `frontend/app/components/factor/FactorResearchWorkspacePage.tsx`
  - obsolete wrapper after canonical route lands
- Delete: `frontend/app/components/factor/FactorPortfolioDeploymentsPage.tsx`
  - obsolete wrapper after canonical route lands
- Delete: `frontend/app/components/factor/FactorLiveGateStatusPage.tsx`
  - obsolete wrapper after canonical route lands
- Delete: `frontend/app/components/factor/FactorLibrary.tsx`
  - only if `rg -n "FactorLibrary" frontend/app -S` still shows no runtime imports except the component itself
- Modify: `backend/scripts/factor_portfolio_smoke.py`
  - make it the canonical workflow smoke entry, including live-gate visibility
- Create: `backend/tests/scripts/test_factor_portfolio_smoke.py`
  - lock smoke-runner behavior with small unit-style tests around request/flow handling
- Modify: `README.md`
  - point server-side verification to the canonical single-flow smoke command
- Modify: `docs/superpowers/plans/2026-03-22-factor-portfolio-go-live-checklist.md`
  - align runbook wording with the canonical smoke command
- Modify: `docs/superpowers/README.md`
  - record the new consolidation plan status once implementation starts/completes

## Verification Targets

- Frontend build still passes:
  - `cd frontend && pnpm build`
- Backend factor regression suite still passes:
  - `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q`
- Backend import smoke still passes:
  - `cd backend && uv run python -c "import main; print('import-ok')"`
- Canonical smoke still passes against a running backend:
  - `cd backend && uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611`
- Stage compatibility works manually in browser:
  - `#factor-pipeline`
  - `#factor-pipeline?stage=deployments`
  - `#factor-pipeline?stage=live-gate`
  - `#factor-research-workspace`
  - `#factor-portfolio-deployments`
  - `#factor-live-gate`

## Implementation Notes

- Preserve the currently validated business line:
  - `Factor Research -> Portfolio Deployments -> Live Gate -> Factor Runtime`
- Old hashes should keep working, but they should no longer define product structure.
- Prefer subtraction over new abstraction. Only split code when it prevents `FactorPipelineWorkspace.tsx` from growing further.
- Keep the factor workspace as the only first-class factor UI. Do not add another page type or another workflow taxonomy.
- If `FactorLibrary.tsx` is still dead after exact search, delete it in the same cleanup pass instead of keeping zombie UI code.
- Keep commits narrow:
  - route/nav consolidation
  - workspace split
  - smoke/doc standardization

### Task 1: Canonicalize The Factor Route And Sidebar Entry

**Files:**
- Modify: `frontend/app/main.tsx`
- Modify: `frontend/app/components/layout/Sidebar.tsx`
- Create: `frontend/app/components/factor/FactorPipelinePage.tsx`
- Test: `frontend/package.json`

- [x] **Step 1: Define the route contract before editing UI**

Document the canonical route contract in code comments or local notes:

- canonical page key: `factor-pipeline`
- supported stages: `research`, `deployments`, `live-gate`
- compatibility aliases:
  - `factor-research-workspace` -> `factor-pipeline?stage=research`
  - `factor-portfolio-deployments` -> `factor-pipeline?stage=deployments`
  - `factor-live-gate` -> `factor-pipeline?stage=live-gate`
  - `factor-library` -> `factor-pipeline?stage=research`

- [x] **Step 2: Update `main.tsx` to normalize old hashes into the canonical route**

Implement:

- `PAGE_TITLES.factor-pipeline`
- route normalization that keeps stage information
- render the new `FactorPipelinePage`
- remove direct rendering branches for the three old factor pages

- [x] **Step 3: Update `Sidebar.tsx` to expose one primary factor entry**

Implement:

- replace the three-item new-flow block with one primary item such as `Factor Pipeline`
- keep old non-factor surfaces available only if still needed, but visually demote them from the main product story
- keep mobile navigation aligned with the new single-entry model instead of three separate factor tabs

- [x] **Step 4: Run frontend build verification**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [x] **Step 5: Manually verify hash compatibility**

Check in browser:

- `#factor-pipeline`
- `#factor-pipeline?stage=deployments`
- `#factor-pipeline?stage=live-gate`
- old hashes redirect or normalize correctly without blank screens

- [x] **Step 6: Commit**

```bash
git add frontend/app/main.tsx frontend/app/components/layout/Sidebar.tsx frontend/app/components/factor/FactorPipelinePage.tsx
git commit -m "refactor: canonicalize factor pipeline entry"
```

### Task 2: Turn The Workspace Into One Staged Flow And Reduce Duplicate UI Shells

**Files:**
- Modify: `frontend/app/components/factor/FactorPipelineWorkspace.tsx`
- Create: `frontend/app/components/factor/pipeline/ResearchStage.tsx`
- Create: `frontend/app/components/factor/pipeline/DeploymentsStage.tsx`
- Create: `frontend/app/components/factor/pipeline/LiveGateStage.tsx`
- Optional Create: `frontend/app/components/factor/pipeline/useFactorPipelineData.ts`
- Delete: `frontend/app/components/factor/FactorResearchWorkspacePage.tsx`
- Delete: `frontend/app/components/factor/FactorPortfolioDeploymentsPage.tsx`
- Delete: `frontend/app/components/factor/FactorLiveGateStatusPage.tsx`
- Optional Delete: `frontend/app/components/factor/FactorLibrary.tsx`
- Test: `frontend/package.json`

- [x] **Step 1: Split render-only stage sections out of `FactorPipelineWorkspace.tsx`**

Extract:

- research summary / run controls / leaderboard content
- deployment list / paper-live actions
- live-gate status cards and checks

Keep the first split purely structural. Do not change backend API contracts in this step.

- [x] **Step 2: Add stage navigation inside the factor page itself**

Implement a simple in-page stage switcher so the user can move through:

1. `Research`
2. `Deployments`
3. `Live Gate`

The page should still deep-link to a stage when `stage=` is present.

- [x] **Step 3: Delete wrapper pages once the canonical page renders all stages**

Delete:

- `frontend/app/components/factor/FactorResearchWorkspacePage.tsx`
- `frontend/app/components/factor/FactorPortfolioDeploymentsPage.tsx`
- `frontend/app/components/factor/FactorLiveGateStatusPage.tsx`

- [x] **Step 4: Remove dead factor-only component(s) if exact search confirms no runtime imports**

Run: `rg -n "FactorLibrary" frontend/app -S`

Expected before deletion:

- only the component definition itself plus unrelated API data helpers inside `SignalManager`

If true, delete `frontend/app/components/factor/FactorLibrary.tsx`.

- [x] **Step 5: Run frontend build verification again**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [x] **Step 6: Commit**

```bash
git add frontend/app/components/factor
git commit -m "refactor: merge factor workflow into staged workspace"
```

### Task 3: Standardize One Canonical Smoke / Regression Entry

**Files:**
- Modify: `backend/scripts/factor_portfolio_smoke.py`
- Create: `backend/tests/scripts/test_factor_portfolio_smoke.py`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-03-22-factor-portfolio-go-live-checklist.md`
- Modify: `docs/superpowers/README.md`
- Test: `backend/tests/scripts/test_factor_portfolio_smoke.py`

- [x] **Step 1: Write failing smoke-runner tests**

Cover at least:

- latest live-gate snapshot is queried and reported when present
- non-200 live-gate responses are surfaced as warnings, not silent skips
- `--trigger-run` still exits non-zero when the latest run completes with `error`

- [x] **Step 2: Run the targeted tests to verify failure**

Run: `cd backend && uv run pytest tests/scripts/test_factor_portfolio_smoke.py -q`

Expected: `FAIL` because the current script does not yet lock the new canonical reporting behavior.

- [x] **Step 3: Extend the smoke runner without changing the core workflow**

Implement:

- live-gate snapshot fetch/reporting via `/api/factor-portfolios/live-gate/latest`
- clearer output sections for:
  - research status
  - latest top portfolio
  - deployment count
  - live-gate decision
- keep paper deployment optional
- keep live deployment out of scope

- [x] **Step 4: Update docs to point to the single canonical command**

Update:

- `README.md`
- `docs/superpowers/plans/2026-03-22-factor-portfolio-go-live-checklist.md`

The docs should stop treating the smoke script as merely "optional helper" and instead present it as the primary fast regression entry for the validated flow.

- [x] **Step 5: Run script/unit verification**

Run:

- `cd backend && uv run pytest tests/scripts/test_factor_portfolio_smoke.py -q`
- `cd backend && uv run python -c "import main; print('import-ok')"`

Expected:

- targeted script tests `PASS`
- import smoke prints `import-ok`

- [x] **Step 6: Run the factor regression suite**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q`

Expected: `PASS`

- [ ] **Step 7: Exercise the canonical smoke command against a running backend**  
Blocked on execution: `localhost:5611` was not serving the backend when the command was run, so the smoke hit `ConnectionRefused` instead of an application-level result.

Run: `cd backend && uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611`

Expected:

- prints current research status
- prints latest portfolio or a no-run warning
- prints deployment summary
- prints live-gate status when available
- exits `0` on healthy read-only checks

- [x] **Step 8: Commit**

```bash
git add backend/scripts/factor_portfolio_smoke.py backend/tests/scripts/test_factor_portfolio_smoke.py README.md docs/superpowers/plans/2026-03-22-factor-portfolio-go-live-checklist.md docs/superpowers/README.md
git commit -m "docs: standardize factor flow smoke verification"
```

### Task 4: Final Verification And Status Reconciliation

**Files:**
- Modify: `docs/superpowers/README.md`
- Test: `frontend/package.json`

- [x] **Step 1: Run end-to-end verification commands**

Run:

- `cd frontend && pnpm build`
- `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py tests/scripts/test_factor_portfolio_smoke.py -q`
- `cd backend && uv run python -c "import main; print('import-ok')"`

Expected:

- frontend build `PASS`
- targeted backend suite `PASS`
- import smoke prints `import-ok`

- [ ] **Step 2: Re-run the smoke command with the canonical path**  
Blocked on execution: the latest run again failed at connect time because no backend was listening on `http://localhost:5611`.

Run: `cd backend && uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611`

Expected: exit `0` with readable stage-by-stage output.

- [x] **Step 3: Update plan status index**

Update `docs/superpowers/README.md` so this plan is no longer "planned" once implementation lands.

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/README.md
git commit -m "docs: reconcile current flow consolidation status"
```

## Deferred Unless A Direct Blocker Appears

- FastAPI lifespan migration for `on_event` deprecation
- Vite chunk-size optimization
- broader removal of Binance / bot / Hyper AI surfaces
- README product-positioning rewrite outside the factor-flow sections
