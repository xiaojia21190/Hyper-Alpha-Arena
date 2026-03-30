# Factor Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `start_local.sh` default to a new `factor` runtime profile that preserves the full Hyperliquid factor workflow while disabling unrelated runtime services and frontend file watching.

**Architecture:** Introduce explicit runtime profile capabilities in settings, split startup into service groups, and let the app boot only the Hyperliquid factor pipeline in `factor` mode. Keep `api` and `full` profiles for diagnostics and compatibility, but move the default server entrypoint to `factor`.

**Tech Stack:** FastAPI, Python 3.12, uvicorn, APScheduler, SQLAlchemy, Hyperliquid client stack, pytest, ruff, shell entry scripts

---

## Execution Status (2026-03-30)

Status: runtime split is implemented, re-verified, and checkpoint commits are completed in this workspace.

Verified:
- Focused runtime/factor suites passed in `backend/`
  - `uv run pytest tests/services/test_runtime_settings.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py tests/services/test_program_execution_service.py tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_technical_indicators.py tests/services/test_scheduler.py tests/api/test_user_routes.py -q`
  - Result: `71 passed`
- Focused portfolio/route regression suites passed in `backend/`
  - `uv run pytest tests/services/test_factor_portfolio_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py -q`
  - Result: `14 passed`
- Static verification passed
  - `uv run ruff check config/settings.py main.py services/startup.py services/factor_portfolio_deployment_service.py tests/services/test_runtime_settings.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py tests/services/test_program_execution_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_service.py`
  - Result: `All checks passed!`
- Syntax verification passed
  - `uv run python -m py_compile main.py config/settings.py services/startup.py services/factor_portfolio_deployment_service.py tests/services/test_runtime_settings.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py tests/services/test_program_execution_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_service.py`
  - Result: exit `0`
- Isolated smoke checks passed
  - `factor`: `NO_PULL=true NO_FRONTEND=true PORT=8803 PID_FILE=.run/uvicorn-factor-smoke.pid LOG_FILE=.run/factor-smoke.log HEALTH_URL=http://127.0.0.1:8803/api/health bash start_local.sh`
  - `factor` endpoints: `/api/health` and `/api/factor-research/status` both returned `200`
  - `factor` log showed `Runtime profile 'factor'` startup with market stream / market flow / factor services only; no Binance collector or strategy manager startup lines
  - `full`: `NO_PULL=true NO_FRONTEND=true PORT=8804 APP_RUNTIME_PROFILE=full PID_FILE=.run/uvicorn-full-smoke.pid LOG_FILE=.run/full-smoke.log HEALTH_URL=http://127.0.0.1:8804/api/health bash start_local.sh`
  - `full` health returned `200`
  - `full` log showed additional Binance collectors and strategy manager startup, which confirms the profile split is observable at runtime
- CPU comparison completed on the same host with 20 samples at 30-second intervals
  - Sampling method: PowerShell `Get-Process` CPU deltas normalized by 16 logical cores
  - `profile=full avg_cpu=0.3048 samples=20 interval=30s`
  - `profile=factor avg_cpu=0.1405 samples=20 interval=30s`
  - `delta_cpu=0.1643`
- Post-review cleanup completed
  - Removed unused `startup_event()` / `shutdown_event()` wrappers from `backend/services/startup.py`
  - Rationale: they were not referenced anywhere in `backend/`, defaulted back to `full`, and the shutdown wrapper incorrectly awaited a synchronous function
  - Fresh regression after cleanup:
    - `uv run pytest tests/services/test_runtime_settings.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py tests/services/test_program_execution_service.py tests/services/test_factor_research_service.py tests/services/test_factor_portfolio_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py tests/api/test_factor_portfolio_routes.py tests/api/test_user_routes.py tests/services/test_technical_indicators.py tests/services/test_scheduler.py -q`
    - Result: `85 passed`
    - `uv run ruff check services/startup.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py`
    - Result: `All checks passed!`
    - `uv run python -m py_compile services/startup.py tests/services/test_startup_profiles.py tests/test_main_runtime_dispatch.py`
    - Result: exit `0`

Pending:
- Startup logs still contain pre-existing SQLite / `information_schema` migration noise that is outside this runtime-split plan.
- Keep `backend/api/user_routes.py` and `backend/tests/api/test_user_routes.py` out of runtime-only commits unless explicitly folded into scope.

## File Map

- Modify: `backend/config/settings.py`
  - add `factor` runtime profile support and explicit booleans/helpers for background, Binance, bot, and factor runtime groups
- Modify: `backend/main.py`
  - route startup/shutdown behavior by profile and keep frontend serving enabled without watcher polling
- Modify: `backend/services/startup.py`
  - split startup/shutdown into grouped helpers and make `factor` profile boot only the required Hyperliquid factor runtime
- Modify: `start_local.sh`
  - default server startup profile becomes `factor`
- Modify: `backend/.env.example`
  - document runtime profile selection and watcher defaults for backend deployments
- Modify: `.env.example`
  - document project-level runtime profile defaults
- Modify: `backend/tests/services/test_runtime_settings.py`
  - cover `factor` profile parsing and grouped runtime flags
- Create: `backend/tests/services/test_startup_profiles.py`
  - verify `factor`, `api`, and `full` startup grouping behavior, including explicit `market_flow` startup/cleanup assertions
- Create: `backend/tests/test_main_runtime_dispatch.py`
  - verify `main.py` startup/shutdown dispatch only restores bot runtime in `full`, not `factor`
- Create: `backend/tests/services/test_program_execution_service.py`
  - verify `price update -> scheduled program trigger` remains live in the `factor` runtime execution chain
- Modify: `backend/tests/services/test_factor_portfolio_deployment_service.py`
  - add regression coverage that deployed factor portfolios remain scheduled Hyperliquid program bindings and verify promotion-gate snapshot source behavior
- Modify: `backend/tests/services/test_factor_research_service.py`
  - add regression coverage that factor automation config remains compatible with the `factor` runtime expectations
- Optional Modify: `backend/services/factor_portfolio_deployment_service.py`
  - only if verification reveals that runtime-specific execution assumptions need hardening
- Optional Modify: `backend/services/program_execution_service.py`
  - only if factor runtime needs a small helper or bugfix to decouple scheduled program execution from unrelated strategy runtime

## Implementation Notes

- Follow @superpowers:test-driven-development discipline for each behavior change.
- Do not delete Binance, bot, or unrelated AI-trading source modules in this plan. Only remove them from the `factor` startup path.
- Keep diffs narrow and reversible.
- Treat the `AccountAssetSnapshot` vs `HyperliquidAccountSnapshot` promotion-gate mismatch as a verification target, not a speculative refactor.
- Do not add a global `exchange == hyperliquid` guard that changes `full` compatibility. If runtime-specific restrictions are required, scope them to `factor` startup behavior or dedicated tests only.

### Task 1: Extend Runtime Profile Settings

**Files:**
- Modify: `backend/config/settings.py`
- Modify: `backend/tests/services/test_runtime_settings.py`
- Test: `backend/tests/services/test_runtime_settings.py`

- [x] **Step 1: Write the failing runtime-profile tests**

```python
def test_runtime_profile_factor_enables_factor_background_services(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="factor")

    assert settings_module.APP_RUNTIME_PROFILE == "factor"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is False
    assert settings_module.BOT_RUNTIME_ENABLED is False


def test_runtime_profile_full_keeps_optional_services(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="full")

    assert settings_module.APP_RUNTIME_PROFILE == "full"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is True
    assert settings_module.BOT_RUNTIME_ENABLED is True
```

- [x] **Step 2: Run the targeted test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_runtime_settings.py -q`
Expected: FAIL because `factor` is not yet a valid profile and grouped runtime flags do not exist.

- [x] **Step 3: Implement minimal profile parsing and grouped runtime flags**

```python
def _get_runtime_profile() -> str:
    raw = os.getenv("APP_RUNTIME_PROFILE", "full").strip().lower()
    return raw if raw in {"api", "factor", "full"} else "full"


APP_RUNTIME_PROFILE = _get_runtime_profile()
BACKGROUND_SERVICES_ENABLED = APP_RUNTIME_PROFILE in {"factor", "full"}
FACTOR_RUNTIME_ENABLED = APP_RUNTIME_PROFILE in {"factor", "full"}
BINANCE_RUNTIME_ENABLED = APP_RUNTIME_PROFILE == "full"
BOT_RUNTIME_ENABLED = APP_RUNTIME_PROFILE == "full"
FRONTEND_WATCHER_ENABLED = _env_bool("FRONTEND_WATCHER_ENABLED", False)
```

- [x] **Step 4: Run the targeted tests to verify they pass**

Run: `cd backend && uv run pytest tests/services/test_runtime_settings.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/config/settings.py backend/tests/services/test_runtime_settings.py
git commit -m "feat: add factor runtime profile settings"
```

### Task 2: Refactor Startup Into Runtime Service Groups

**Files:**
- Modify: `backend/services/startup.py`
- Create: `backend/tests/services/test_startup_profiles.py`
- Test: `backend/tests/services/test_startup_profiles.py`

- [x] **Step 1: Write failing startup-group tests**

```python
def test_initialize_services_factor_profile_starts_only_factor_runtime(monkeypatch):
    started = []

    monkeypatch.setattr(startup_module, "_start_scheduler_services", lambda: started.append("scheduler"))
    monkeypatch.setattr(startup_module, "_start_hyperliquid_factor_market_services", lambda: started.append("hyperliquid"))
    monkeypatch.setattr(startup_module, "_start_factor_services", lambda: started.append("factor"))
    monkeypatch.setattr(startup_module, "_start_program_execution_services", lambda: started.append("program"))
    monkeypatch.setattr(startup_module, "_start_binance_services", lambda: started.append("binance"))
    monkeypatch.setattr(startup_module, "_start_bot_services", lambda: started.append("bot"))

    startup_module.initialize_services("factor")

    assert started == ["scheduler", "hyperliquid", "factor", "program"]


def test_hyperliquid_factor_market_services_start_market_flow_and_cleanup(monkeypatch):
    calls = []

    monkeypatch.setattr(startup_module, "start_market_stream", lambda *args, **kwargs: calls.append("market_stream"))
    monkeypatch.setattr(startup_module, "subscribe_price_updates", lambda handler: calls.append("price_subscriber"))
    monkeypatch.setattr(startup_module.task_scheduler, "add_interval_task", lambda **kwargs: calls.append(kwargs["task_id"]))
    monkeypatch.setattr("services.market_flow_collector.market_flow_collector.start", lambda: calls.append("market_flow_start"))

    startup_module._start_hyperliquid_factor_market_services()

    assert "market_flow_start" in calls
    assert "market_flow_data_cleanup" in calls


def test_program_execution_services_wire_price_subscription_and_shutdown(monkeypatch):
    subscribed = []
    unsubscribed = []

    monkeypatch.setattr(startup_module, "subscribe_price_updates", lambda handler: subscribed.append(handler.__name__))
    monkeypatch.setattr(startup_module, "unsubscribe_price_updates", lambda handler: unsubscribed.append(handler.__name__))

    startup_module._start_program_execution_services()
    startup_module._stop_program_execution_services()

    assert any("program" in name for name in subscribed)
    assert unsubscribed
```

- [x] **Step 2: Run the targeted test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_startup_profiles.py -q`
Expected: FAIL because `initialize_services()` does not yet accept grouped runtime dispatch.

- [x] **Step 3: Implement grouped startup/shutdown helpers**

```python
def initialize_services(profile: str = "full"):
    _start_scheduler_services()

    if profile in {"factor", "full"}:
        _start_hyperliquid_factor_market_services()
        _start_factor_services()
        _start_program_execution_services()

    if profile == "full":
        _start_binance_services()
```

```python
def shutdown_services(profile: str = "full"):
    if profile == "full":
        _stop_binance_services()

    if profile in {"factor", "full"}:
        _stop_program_execution_services()
        _stop_hyperliquid_factor_market_services()
        _stop_factor_services()

    stop_scheduler()
```

Keep the grouped helpers concrete enough that tests can assert `market_flow_collector.start()` and cleanup task registration directly, not just abstract group names.

- [x] **Step 4: Run the targeted tests to verify they pass**

Run: `cd backend && uv run pytest tests/services/test_startup_profiles.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/services/startup.py backend/tests/services/test_startup_profiles.py
git commit -m "refactor: split runtime startup by profile"
```

### Task 3: Wire `main.py` Startup And Shutdown To The `factor` Runtime

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_main_runtime_dispatch.py`
- Test: `backend/tests/test_main_runtime_dispatch.py`

- [x] **Step 1: Write failing startup-dispatch tests for `main.py`**

```python
def test_factor_runtime_startup_skips_bot_restore(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", True)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")
    monkeypatch.setattr(main_module, "BOT_RUNTIME_ENABLED", False)
    monkeypatch.setattr("services.startup.initialize_services", lambda profile: calls.append(("init", profile)))

    main_module.on_startup()

    assert calls == [("init", "factor")]


async def test_factor_runtime_skips_telegram_discord_startup_and_shutdown(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module, "BOT_RUNTIME_ENABLED", False)
    await main_module.restore_bot_webhooks()
    await main_module.restore_discord_gateway()
    await main_module.shutdown_discord_gateway()

    assert calls == []
```

```python
async def test_full_runtime_allows_telegram_discord_lifecycle(monkeypatch):
    calls = []

    monkeypatch.setattr(main_module, "BOT_RUNTIME_ENABLED", True)
    monkeypatch.setattr("services.telegram_bot_service.restore_telegram_webhook", fake_async(lambda: calls.append("telegram_start")))
    monkeypatch.setattr("services.discord_bot_service.start_discord_gateway", fake_async(lambda *args, **kwargs: calls.append("discord_start")))
    monkeypatch.setattr("services.discord_bot_service.stop_discord_gateway", fake_async(lambda: calls.append("discord_stop")))

    await main_module.restore_bot_webhooks()
    await main_module.restore_discord_gateway()
    await main_module.shutdown_discord_gateway()

    assert "telegram_start" in calls
    assert "discord_stop" in calls
```

The exact async mocking can vary. The required assertion is: `factor` does not route into bot restore, while `full` still can.

- [x] **Step 2: Run the relevant tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_main_runtime_dispatch.py -q`
Expected: FAIL until `main.py` is aligned on grouped runtime dispatch.

- [x] **Step 3: Update startup/shutdown dispatch in `main.py`**

```python
if FRONTEND_WATCHER_ENABLED:
    start_frontend_watcher()

if BACKGROUND_SERVICES_ENABLED:
    from services.startup import initialize_services
    initialize_services(APP_RUNTIME_PROFILE)

if BOT_RUNTIME_ENABLED:
    await restore_telegram_webhook()
    await restore_discord_gateway()
```

```python
if BACKGROUND_SERVICES_ENABLED:
    from services.startup import shutdown_services
    shutdown_services(APP_RUNTIME_PROFILE)

if BOT_RUNTIME_ENABLED:
    await stop_discord_gateway()
```

- [x] **Step 4: Run the runtime-setting and syntax verification**

Run: `cd backend && uv run pytest tests/test_main_runtime_dispatch.py -q`
Expected: PASS

Run: `cd backend && uv run python -m py_compile main.py`
Expected: no output, exit code `0`

- [x] **Step 5: Commit**

```bash
git add backend/main.py backend/tests/test_main_runtime_dispatch.py
git commit -m "feat: route app startup through factor runtime profile"
```

### Task 4: Make `factor` The Default Server Entry Profile

**Files:**
- Modify: `start_local.sh`
- Modify: `backend/.env.example`
- Modify: `.env.example`

- [x] **Step 1: Update the shell entrypoint default**

```bash
APP_PORT="${PORT:-8000}" \
APP_RUNTIME_PROFILE="${APP_RUNTIME_PROFILE:-factor}" \
FRONTEND_WATCHER_ENABLED="${FRONTEND_WATCHER_ENABLED:-false}" \
exec bash "${ROOT_DIR}/scripts/deploy_prod.sh"
```

- [x] **Step 2: Update environment templates to document the new default**

```env
APP_RUNTIME_PROFILE=factor
FRONTEND_WATCHER_ENABLED=false
```

- [x] **Step 3: Verify the file contents manually**

Run: `rg -n "APP_RUNTIME_PROFILE|FRONTEND_WATCHER_ENABLED" start_local.sh backend/.env.example .env.example`
Expected: `start_local.sh` defaults to `factor`, and both env templates document watcher-off server startup.

- [x] **Step 4: Run a quick syntax-safe shell verification**

Run: `bash -n start_local.sh`
Expected: no output, exit code `0`

- [x] **Step 5: Commit**

```bash
git add start_local.sh backend/.env.example .env.example
git commit -m "chore: default local server startup to factor runtime"
```

### Task 5: Lock The Factor Deployment Execution Path

**Files:**
- Create: `backend/tests/services/test_program_execution_service.py`
- Modify: `backend/tests/services/test_factor_portfolio_deployment_service.py`
- Modify: `backend/tests/services/test_factor_research_service.py`
- Optional Modify: `backend/services/factor_portfolio_deployment_service.py`
- Optional Modify: `backend/services/program_execution_service.py`
- Test: `backend/tests/services/test_program_execution_service.py`
- Test: `backend/tests/services/test_factor_portfolio_deployment_service.py`
- Test: `backend/tests/services/test_factor_research_service.py`

- [x] **Step 1: Add failing regression tests for scheduled execution and deployment assumptions**

```python
def test_program_execution_service_triggers_scheduled_binding_on_price_update(monkeypatch):
    service = ProgramExecutionService()
    executed = []

    monkeypatch.setattr(service, "_refresh_binding_cache", lambda: service._binding_states.update({
        1: {
            "binding_id": 1,
            "account_id": 7,
            "program_id": 9,
            "trigger_interval": 60,
            "last_trigger_at": datetime.now(timezone.utc) - timedelta(seconds=3600),
            "signal_pool_ids": [],
        }
    }))
    monkeypatch.setattr(service, "_execute_scheduled_trigger", lambda binding_id, symbol, event_time: executed.append(binding_id))

    service.on_price_update("BTC", 100000.0, datetime.now(timezone.utc))

    assert executed == [1]
```

If a lightweight real DB path is practical, prefer an integration-style variant that confirms a `ProgramExecutionLog` row is written after the scheduled path runs. If not, keep this unit test and add a manual smoke step in Task 6.

```python
def test_deploy_portfolio_creates_scheduled_hyperliquid_binding(db_session):
    result = deploy_portfolio_candidate(
        db_session,
        portfolio_id=portfolio_id,
        account_id=account_id,
        mode="paper",
        exchange="hyperliquid",
    )

    assert result["binding"]["id"] > 0
    binding = db_session.query(AccountProgramBinding).get(result["binding"]["id"])
    assert binding.exchange == "hyperliquid"
    assert binding.scheduled_trigger_enabled is True
    assert binding.trigger_interval >= 30
```

- [x] **Step 2: Run the targeted tests to verify they fail or expose missing assumptions**

Run: `cd backend && uv run pytest tests/services/test_program_execution_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_service.py -q`
Expected: either FAIL or reveal missing explicit guarantees in deployment/runtime assumptions.

- [x] **Step 3: Implement only the minimal fixes needed**

```python
binding = AccountProgramBinding(
    account_id=account_id,
    program_id=program.id,
    trigger_interval=max(int(trigger_interval), 30),
    scheduled_trigger_enabled=True,
    is_active=True,
    exchange=exchange,
)
```

Avoid adding a global hard error for non-Hyperliquid exchange in shared deployment code. If a runtime-specific guard is required, scope it to `factor` profile behavior or test fixtures only.

- [x] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_program_execution_service.py tests/services/test_factor_portfolio_deployment_service.py tests/services/test_factor_research_service.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/tests/services/test_program_execution_service.py backend/tests/services/test_factor_portfolio_deployment_service.py backend/tests/services/test_factor_research_service.py backend/services/factor_portfolio_deployment_service.py backend/services/program_execution_service.py
git commit -m "test: lock factor deployment runtime assumptions"
```

### Task 6: Verify And Decide The Live-Gate Snapshot Source

**Files:**
- Modify: `backend/tests/services/test_factor_portfolio_deployment_service.py`
- Optional Modify: `backend/services/factor_portfolio_deployment_service.py`
- Test: `backend/tests/services/test_factor_portfolio_deployment_service.py`

- [x] **Step 1: Add a failing regression test for the promotion gate snapshot source**

```python
def test_live_promotion_gate_uses_expected_snapshot_source(monkeypatch):
    service = FactorPortfolioDeploymentService(db=fake_db)

    # Build fixture data so the chosen query path is observable.
    # Assert the gate reads the intended snapshot model for HY runtime.
```

The task must end with an explicit decision artifact:

- `verified source = AccountAssetSnapshot` or
- `verified source = HyperliquidAccountSnapshot`

with the evidence tied to `_resolve_paper_gate_context()` behavior and the corresponding regression test. Do not accept a 鈥渄ocumented mismatch鈥?without a concrete correctness decision.

- [x] **Step 2: Run the targeted test and inspect the actual data path**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_deployment_service.py -q`
Expected: reveal the actual source path and force an explicit correctness decision.

- [x] **Step 3: Implement the minimal change if the source is wrong**

Only change the gate query if the test proves the current source is incorrect for HY factor runtime. Keep the fix tightly scoped.

- [x] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_portfolio_deployment_service.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add backend/tests/services/test_factor_portfolio_deployment_service.py backend/services/factor_portfolio_deployment_service.py
git commit -m "test: verify factor live gate snapshot source"
```

### Task 7: Verify The Full `factor` Runtime Matrix

**Files:**
- Modify: `backend/tests/services/test_runtime_settings.py`
- Modify: `backend/tests/services/test_startup_profiles.py`
- Modify: `backend/tests/test_main_runtime_dispatch.py`
- Modify: `backend/tests/services/test_program_execution_service.py`
- Test: `backend/tests/services/test_runtime_settings.py`
- Test: `backend/tests/services/test_startup_profiles.py`
- Test: `backend/tests/test_main_runtime_dispatch.py`
- Test: `backend/tests/services/test_program_execution_service.py`
- Test: `backend/tests/services/test_factor_research_service.py`
- Test: `backend/tests/services/test_factor_portfolio_service.py`
- Test: `backend/tests/services/test_factor_portfolio_deployment_service.py`
- Test: `backend/tests/services/test_factor_research_integration.py`
- Test: `backend/tests/api/test_factor_research_routes.py`
- Test: `backend/tests/api/test_factor_portfolio_routes.py`

- [x] **Step 1: Run the focused runtime and factor suites**

Run:

```bash
cd backend && uv run pytest \
  tests/services/test_runtime_settings.py \
  tests/services/test_startup_profiles.py \
  tests/test_main_runtime_dispatch.py \
  tests/services/test_program_execution_service.py \
  tests/services/test_factor_research_service.py \
  tests/services/test_factor_portfolio_service.py \
  tests/services/test_factor_portfolio_deployment_service.py \
  tests/services/test_factor_research_integration.py \
  tests/api/test_factor_research_routes.py \
  tests/api/test_factor_portfolio_routes.py -q
```

Expected: PASS

- [x] **Step 2: Run static verification on touched runtime files**

Run:

```bash
cd backend && uv run ruff check \
  config/settings.py \
  main.py \
  services/startup.py \
  services/program_execution_service.py \
  services/factor_portfolio_deployment_service.py \
  tests/services/test_runtime_settings.py \
  tests/services/test_startup_profiles.py \
  tests/test_main_runtime_dispatch.py \
  tests/services/test_program_execution_service.py
```

Expected: `All checks passed!`

- [x] **Step 3: Run syntax verification for touched Python files**

Run:

```bash
cd backend && uv run python -m py_compile \
  main.py \
  config/settings.py \
  services/startup.py \
  services/program_execution_service.py \
  services/factor_portfolio_deployment_service.py \
  tests/services/test_runtime_settings.py \
  tests/services/test_startup_profiles.py \
  tests/test_main_runtime_dispatch.py \
  tests/services/test_program_execution_service.py
```

Expected: no output, exit code `0`

- [x] **Step 4: Manual runtime smoke check**

Run:

```bash
# from repo root
bash start_local.sh
```

Then verify:

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/factor-research/status
```

Expected:
- health endpoint responds
- factor research status endpoint responds
- logs show factor runtime groups starting
- logs do not show Binance or bot services starting
- deployed scheduled factor program can still be exercised through the price-update path or equivalent manual trigger

- [x] **Step 5: Record a CPU comparison between `full` and `factor`**

Run on the same host, same idle observation window:

```bash
# profile A
APP_RUNTIME_PROFILE=full bash start_local.sh
# sample the backend process every 30s for 10 minutes and record the average CPU

# profile B
APP_RUNTIME_PROFILE=factor bash start_local.sh
# sample the backend process every 30s for 10 minutes and record the average
```

Sampling method:

```bash
PID="$(cat .run/uvicorn.pid)"
for i in $(seq 1 20); do
  ps -p "${PID}" -o %cpu= | tr -d " "
  sleep 30
done
```

Report format:

```text
profile=full avg_cpu=<value> samples=20 interval=30s
profile=factor avg_cpu=<value> samples=20 interval=30s
delta_cpu=<full-minus-factor>
```

Expected:
- `factor` average CPU is lower than `full`
- record the measurement in the final report even if no hard threshold is enforced yet

- [x] **Step 6: Commit**

```bash
git add .
git commit -m "feat: add factor-focused runtime profile"
```

## Review Checklist

- The `factor` profile starts only the Hyperliquid factor pipeline and deployed-program runtime.
- `start_local.sh` defaults to `factor`.
- The frontend remains served but no watcher starts on the server.
- Binance and bot startup paths are not entered in `factor` mode.
- Deployed factor portfolios still execute automatically on Hyperliquid testnet.
- No large source deletion is bundled into this runtime split.

