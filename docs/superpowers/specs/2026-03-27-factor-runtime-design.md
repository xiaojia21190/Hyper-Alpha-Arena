# Factor Runtime Design

Date: 2026-03-27

## Goal

Reshape the application runtime around the current business-critical workflow only:

- frontend enabled
- API enabled
- manual factor generation, research, portfolio construction, backtest, and selection
- periodic automatic factor research, selection, and deployment
- deployed Hyperliquid testnet portfolio programs continue running automatically
- no frontend file watching on the server
- no Binance, bot, or unrelated AI trading services by default

The runtime must preserve the factor pipeline end-to-end while reducing CPU usage by removing unrelated always-on services from the default startup path.

## Current Problem

`start_local.sh` currently acts as the server entrypoint. After the earlier CPU mitigation, it defaults to an `api` profile. That profile is too narrow for the real production workflow:

- factor APIs still exist
- factor research can still be triggered manually
- portfolio deployment still writes `TradingProgram` and `AccountProgramBinding`
- but the runtime no longer starts the background services required for deployed HY paper/test strategies to keep executing

The inverse problem also exists in the old `full` runtime:

- it starts the entire mixed stack
- Hyperliquid factor services, Binance collectors, bot restores, and unrelated AI trading services all start together
- CPU usage becomes too high for the target server

## Runtime Profiles

Keep three explicit runtime profiles:

- `api`
  - frontend static assets + API only
  - near-zero background services
  - useful for diagnostics or pure admin usage
- `factor`
  - the new default profile
  - only the services required for the factor pipeline and HY testnet automated runtime
- `full`
  - legacy full-stack compatibility profile
  - keeps the current broad startup behavior available as a fallback

## Default Startup Behavior

`start_local.sh` should default to:

- `APP_RUNTIME_PROFILE=factor`
- `FRONTEND_WATCHER_ENABLED=false`

This keeps the frontend available on the server but removes watcher/build polling.

## Services Required In `factor` Profile

### Core app

- FastAPI app
- frontend static serving
- DB initialization, migrations, prompt/template seed, system config initialization

### Runtime scheduling

- `scheduler`
- Hyperliquid symbol refresh scheduling
- factor research scheduler
- factor computation/effectiveness scheduling

### Hyperliquid market runtime

- `market_stream`
  - needed to emit periodic price updates
- `market_flow_collector`
  - required for microstructure factors such as `CVD`, `OI`, `FUNDING`, `TAKER`, and `DEPTH`
- `hyperliquid_snapshot_service`
  - required for HY account state snapshots and parts of the deployment observation/gating flow

### Factor pipeline

- `factor_computation_service`
- `factor_effectiveness_service`
- `factor_research_automation_service`
- factor portfolio deployment services
- factor backtest services

### Deployment execution chain

- `program_execution_service`
  - deployed factor portfolios are materialized as `TradingProgram + AccountProgramBinding`
  - scheduled execution uses `ProgramExecutionService`
- price-update subscription wiring for `ProgramExecutionService`
- Hyperliquid trading client / environment / wallet dependencies

## Services Disabled In `factor` Profile

- Binance symbol refresh
- Binance REST collector
- Binance websocket collector
- Binance snapshot service
- Telegram restore
- Discord restore
- bot runtime startup
- unrelated AI trading strategy runtime
- unrelated broadcast/background tasks that are not part of the factor pipeline
- frontend file watcher

## Important Dependency Notes

### Market flow cannot be removed

The factor registry contains microstructure factors implemented through `market_flow_indicators`. Removing `market_flow_collector` would silently shrink the usable factor set and invalidate the current research pipeline.

### Program execution must remain

Portfolio deployment does not directly execute trades. It creates programs and account bindings. Automatic HY testnet execution after deployment depends on `ProgramExecutionService` receiving scheduled or signal-driven triggers.

### Avoid unnecessary retention of legacy strategy runtime

The old AI strategy manager should not remain in the `factor` profile unless a concrete dependency is proven. The target pipeline is factor-program execution, not the legacy mixed AI trading path.

## Suspected Risk To Verify During Implementation

The auto-promotion gate currently reads from `AccountAssetSnapshot`, while HY external account snapshotting primarily writes `HyperliquidAccountSnapshot`. This may indicate a mixed legacy/new snapshot model path in promotion logic.

Implementation must verify:

- whether HY testnet portfolio observation uses the correct snapshot source
- whether `AccountAssetSnapshot` is still required for the factor deployment gate
- whether the gate should be migrated fully to `HyperliquidAccountSnapshot`

This is a functional-risk item, not just cleanup.

## Code Cleanup Strategy

Do not delete large amounts of code in the same change as the runtime split.

### Phase 1: isolate startup behavior

- add the `factor` runtime profile
- refactor startup into explicit service groups
- make `factor` the default server entrypoint
- verify factor pipeline behavior end-to-end

### Phase 2: remove dead startup paths

- remove startup references for disabled Binance/bot/unrelated services from the `factor` path
- keep source modules in place until runtime verification is stable

### Phase 3: delete unused code

Delete in small batches, with verification after each batch:

1. Binance runtime/backend/frontend paths
2. bot/Telegram/Discord runtime
3. unrelated AI trading runtime
4. unused frontend screens and APIs outside the factor workflow

## Implementation Plan Shape

### Step 1

Extend runtime profile settings from `api/full` to `api/factor/full`.

### Step 2

Refactor `services/startup.py` into grouped startup/shutdown helpers:

- core scheduler services
- Hyperliquid factor market services
- factor services
- deployment execution services
- optional Binance services
- optional bot services

### Step 3

Update `main.py` to dispatch startup/shutdown behavior by profile.

### Step 4

Update `start_local.sh` so the default profile is `factor`.

### Step 5

Add tests covering runtime profile selection and startup grouping.

### Step 6

Run factor-focused verification:

- factor research service tests
- factor portfolio service tests
- factor portfolio deployment tests
- factor route tests
- startup/runtime setting tests

## Acceptance Criteria

- `bash start_local.sh` defaults to `factor` runtime
- frontend is available
- frontend watcher is off
- factor research can be triggered manually
- periodic factor automation can be enabled and scheduled
- portfolio deployment to HY testnet still auto-runs after deployment
- unrelated Binance/bot services do not start in `factor` mode
- CPU usage is materially lower than the old `full` default

## Out Of Scope For This Change

- deleting all legacy code immediately
- redesigning the factor strategy format
- changing factor research algorithms
- changing the portfolio scoring model
- changing the live-promotion business rules beyond necessary bug fixes discovered during verification
