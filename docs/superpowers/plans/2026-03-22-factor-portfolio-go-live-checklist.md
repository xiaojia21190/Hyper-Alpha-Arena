# Factor Portfolio Go-Live Checklist

**Goal:** Provide a deterministic operator checklist for `research -> portfolio winner -> paper deploy -> live deploy gate` using the current project APIs.

---

## Execution Status (2026-03-30)

Status: active operator runbook for the current branch.

Notes:

- This file is not an implementation backlog. It remains relevant as a verification and rehearsal checklist for the delivered factor portfolio flow.
- The APIs and runtime flow referenced here exist on the current branch:
  - `/api/factor-research/*`
  - `/api/factor-portfolios/*`
  - deployed program bindings via the factor runtime profile
- Re-run the commands in Section 2 before using this as a release/go-live gate, because the historical PASS notes in related plans are snapshots, not standing guarantees.

## 1) Preflight

- Ensure backend is running and reachable.
- Ensure DB migrations are applied (including factor portfolio tables).
- Ensure target account already exists and has exchange credentials configured.

Recommended backend env flags:

```env
FACTOR_RESEARCH_ENABLED=true
FACTOR_RESEARCH_RUN_ON_STARTUP=false
FACTOR_RESEARCH_AUTO_PROMOTE_PAPER=false
FACTOR_RESEARCH_REQUIRE_LIVE_CONFIRM=true
```

---

## 2) Verification Gate (must pass)

```bash
cd backend
uv run ruff check .
uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q
uv run pytest -q
uv run python -c "import main; print('import-ok')"
```

Expected:

- `ruff` clean.
- Factor portfolio targeted suite passes.
- Full backend suite passes.
- Import smoke returns `import-ok`.

---

## 2.5) Canonical Smoke / Fast Regression Entry

Use `backend/scripts/factor_portfolio_smoke.py` as the first smoke and quick regression entry for the current factor portfolio flow. The staged output should report:

- `research status`
- `latest portfolio`
- `deployment summary`
- `live-gate decision`

Read-only snapshot:

```bash
cd backend
uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611
```

Trigger a full run and wait:

```bash
cd backend
uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611 --trigger-run
```

Lightweight local rehearsal (faster):

```bash
cd backend
uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611 --trigger-run --top-n-symbols 3 --lookback-days 7 --prescreen-limit 2 --wait-timeout 180 --poll-seconds 2
```

Trigger + deploy paper:

```bash
cd backend
uv run python scripts/factor_portfolio_smoke.py --base-url http://localhost:5611 --trigger-run --deploy-paper-account-id 2
```

Interpretation:

- `research status` confirms scheduler state and latest run outcome.
- `latest portfolio` confirms the newest winner snapshot and candidate visibility.
- `deployment summary` shows the recent paper/live deployment footprint.
- `live-gate decision` surfaces the latest gate snapshot, and any non-200 response must show as a warning instead of silently disappearing.

---

## 3) Trigger Research Run

`POST /api/factor-research/run`

Example:

```bash
curl -X POST "http://localhost:5611/api/factor-research/run" ^
  -H "Content-Type: application/json" ^
  -d "{\"exchange\":\"hyperliquid\",\"top_n_symbols\":20,\"lookback_days\":180,\"objective\":\"return_over_drawdown\",\"factor_scope\":\"builtin_only\",\"period\":\"1h\",\"prescreen_limit\":10,\"auto_promote_paper\":false,\"paper_account_id\":0}"
```

Then poll:

`GET /api/factor-research/status`

Run is complete when:

- `status` becomes `idle`
- `last_run_status` is `success`
- `last_top_portfolio` is not null

---

## 4) Select Winner

- `GET /api/factor-portfolios/latest` to fetch latest successful run.
- Record winner `portfolio_id` from `top_portfolio`.
- Optional deep inspection: `GET /api/factor-portfolios/runs/{run_id}`.

---

## 5) Deploy To Paper First

`POST /api/factor-portfolios/{portfolio_id}/deploy-paper`

Example:

```bash
curl -X POST "http://localhost:5611/api/factor-portfolios/123/deploy-paper" ^
  -H "Content-Type: application/json" ^
  -d "{\"account_id\":2,\"period\":\"1h\",\"trigger_interval\":3600,\"signal_pool_ids\":[],\"exchange\":\"hyperliquid\"}"
```

Expected response:

- `deployment.mode = "paper"`
- `deployment.status = "deployed"`
- `program.id` and `binding.id` returned

---

## 6) Observe Paper Runtime

- `GET /api/factor-portfolios/deployments?account_id={id}` confirms deployment record.
- Verify Program Trader binding exists and is active.
- Observe at least one scheduled cycle before considering live promotion.

---

## 7) Live Deployment Gate (manual confirmation required)

`POST /api/factor-portfolios/{portfolio_id}/deploy-live`

`confirm_live` must be `true` or request is rejected.

Example:

```bash
curl -X POST "http://localhost:5611/api/factor-portfolios/123/deploy-live" ^
  -H "Content-Type: application/json" ^
  -d "{\"account_id\":2,\"period\":\"1h\",\"trigger_interval\":3600,\"signal_pool_ids\":[],\"exchange\":\"hyperliquid\",\"confirm_live\":true}"
```

Safety rule:

- Never enable automatic live promotion.
- Always run paper first and verify runtime health.

---

## 8) Rollback / Stop

- Disable affected binding (or pause scheduler path for target account/program).
- If needed, redeploy last known-good portfolio to paper.
- Keep deployment history via `/api/factor-portfolios/deployments` for audit trail.
