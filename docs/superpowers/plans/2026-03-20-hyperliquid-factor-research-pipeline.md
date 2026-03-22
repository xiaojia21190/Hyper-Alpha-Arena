# Hyperliquid Factor Research Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend research pipeline that resolves Hyperliquid top-20 symbols by 24h volume, evaluates built-in factors over 180 days, batch-backtests them with one shared Program Trader template, and ranks them by return over drawdown.

**Architecture:** Add one orchestration service that reuses the existing factor effectiveness service and `ProgramBacktestEngine`, but does not depend on an existing trader binding. Extend Hyperliquid market data with a batch 24h ticker fetch for volume ranking, extend factor effectiveness to accept an explicit symbol list, then expose the research run through a thin API route and a direct Python invocation path for manual verification.

**Tech Stack:** FastAPI, SQLAlchemy, existing `backend/backtest/*` engine, Hyperliquid native `metaAndAssetCtxs` API, `uv`, `pytest`

---

## File Structure

### New files

- `backend/services/factor_research_service.py`
  - Own the research orchestration flow:
    - top-volume universe selection
    - built-in factor discovery
    - prescreening
    - percentile threshold computation
    - scheduled-only backtest config generation
    - result scoring and ranking
- `backend/api/factor_research_routes.py`
  - Expose a thin backend-only entrypoint for running the research pipeline
- `backend/tests/services/test_factor_research_service.py`
  - Unit tests for factor discovery, universe sorting, score calculation, threshold logic, and orchestration glue
- `backend/tests/services/test_factor_effectiveness_service.py`
  - Unit tests for explicit-symbol effectiveness computation hooks
- `backend/tests/api/test_factor_research_routes.py`
  - Route-level tests for request validation and service delegation
- `backend/tests/services/test_factor_research_integration.py`
  - Small mocked end-to-end research pipeline test

### Modified files

- `backend/services/hyperliquid_market_data.py`
  - Add batch ticker fetch support from `metaAndAssetCtxs`
  - Expose top-volume symbol metadata suitable for ranking
- `backend/services/factor_effectiveness_service.py`
  - Allow research runs to compute effectiveness for explicit symbols instead of watchlist-only selection
- `backend/main.py`
  - Include the new factor research router

## Implementation Notes

- Do not change the existing `POST /api/programs/backtest` contract for research use. That endpoint is binding-driven and derives symbols from signal pools.
- The research flow should call `ProgramBacktestEngine` directly with:
  - `signal_pool_ids=[]`
  - `scheduled_interval_sec=3600`
  - explicit `symbols`
  - generated strategy code
- Do not reuse the Hyperliquid selected-symbol watchlist for the top-20 research universe. The watchlist is capped and user-facing.
- Keep all factor comparisons on one shared strategy template. Only factor name, direction mapping, and percentiles may vary per factor.

---

### Task 1: Add Pure Research Helper Tests And Service Skeleton

**Files:**
- Create: `backend/tests/services/test_factor_research_service.py`
- Create: `backend/services/factor_research_service.py`

- [ ] **Step 1: Write the failing unit tests for pure helper behavior**

```python
from services.factor_research_service import (
    calculate_return_over_drawdown_score,
    rank_factor_results,
    collect_builtin_factor_names,
)


def test_return_over_drawdown_uses_floor_value():
    result = calculate_return_over_drawdown_score(
        total_pnl_percent=12.0,
        max_drawdown_percent=0.0,
        floor_value=1.0,
    )
    assert result == 12.0


def test_rank_factor_results_uses_tie_breakers():
    ranked = rank_factor_results([
        {"factor_name": "A", "score": 4.0, "sharpe_ratio": 1.1, "total_pnl_percent": 10.0, "total_trades": 20},
        {"factor_name": "B", "score": 4.0, "sharpe_ratio": 1.4, "total_pnl_percent": 9.0, "total_trades": 10},
    ])
    assert ranked[0]["factor_name"] == "B"


def test_collect_builtin_factor_names_includes_builtin_expression_rows():
    names = collect_builtin_factor_names(
        registry_names=["RSI14"],
        builtin_expression_names=["EMA_CROSS_7_21"],
    )
    assert names == ["EMA_CROSS_7_21", "RSI14"]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `FAIL` because `factor_research_service.py` and the tested functions do not exist yet.

- [ ] **Step 3: Write the minimal service skeleton and pure helper implementations**

```python
def calculate_return_over_drawdown_score(total_pnl_percent: float, max_drawdown_percent: float, floor_value: float = 1.0) -> float:
    return total_pnl_percent / max(max_drawdown_percent, floor_value)


def collect_builtin_factor_names(registry_names: list[str], builtin_expression_names: list[str]) -> list[str]:
    return sorted(set(registry_names) | set(builtin_expression_names))


def rank_factor_results(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("score", float("-inf")),
            row.get("sharpe_ratio", float("-inf")),
            row.get("total_pnl_percent", float("-inf")),
            row.get("total_trades", float("-inf")),
        ),
        reverse=True,
    )
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the green helper baseline**

```bash
git add backend/tests/services/test_factor_research_service.py backend/services/factor_research_service.py
git commit -m "feat: scaffold factor research service helpers"
```

### Task 2: Add Hyperliquid Top-Volume Universe Resolution

**Files:**
- Modify: `backend/services/hyperliquid_market_data.py`
- Modify: `backend/services/factor_research_service.py`
- Modify: `backend/tests/services/test_factor_research_service.py`

- [ ] **Step 1: Write the failing tests for top-volume sorting and symbol filtering**

```python
from services.factor_research_service import sort_symbols_by_volume


def test_sort_symbols_by_volume_descending():
    symbols = sort_symbols_by_volume([
        {"symbol": "ETH", "volume24h": 10},
        {"symbol": "BTC", "volume24h": 20},
        {"symbol": "DOGE", "volume24h": 5},
    ], limit=2)
    assert symbols == ["BTC", "ETH"]


def test_sort_symbols_by_volume_skips_missing_symbol_or_volume():
    symbols = sort_symbols_by_volume([
        {"symbol": "BTC", "volume24h": 20},
        {"symbol": "", "volume24h": 30},
        {"symbol": "ETH", "volume24h": None},
    ], limit=5)
    assert symbols == ["BTC"]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `FAIL` because `sort_symbols_by_volume()` and the batch ticker path are not implemented yet.

- [ ] **Step 3: Implement the batch market-data fetch and research universe resolver**

```python
# in hyperliquid_market_data.py
def get_all_ticker_data_from_hyperliquid(environment: str = "mainnet") -> list[dict]:
    # one metaAndAssetCtxs call -> rows with symbol + volume24h
    ...


# in factor_research_service.py
def sort_symbols_by_volume(rows: list[dict], limit: int) -> list[str]:
    ...


def resolve_top_hyperliquid_symbols(limit: int = 20) -> list[str]:
    rows = get_all_ticker_data_from_hyperliquid("mainnet")
    return sort_symbols_by_volume(rows, limit)
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the universe resolver**

```bash
git add backend/services/hyperliquid_market_data.py backend/services/factor_research_service.py backend/tests/services/test_factor_research_service.py
git commit -m "feat: add hyperliquid top-volume universe resolver"
```

### Task 3: Extend Factor Effectiveness For Explicit Research Symbols

**Files:**
- Create: `backend/tests/services/test_factor_effectiveness_service.py`
- Modify: `backend/services/factor_effectiveness_service.py`

- [ ] **Step 1: Write the failing tests for explicit-symbol effectiveness selection**

```python
from services.factor_effectiveness_service import FactorEffectivenessService


def test_get_symbols_uses_explicit_override():
    service = FactorEffectivenessService()
    symbols = service._normalize_symbols_override(["BTC", "ETH", "btc"])
    assert symbols == ["BTC", "ETH"]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_effectiveness_service.py -v`

Expected: `FAIL` because the explicit-symbol override helpers do not exist yet.

- [ ] **Step 3: Implement explicit-symbol research hooks in the effectiveness service**

```python
class FactorEffectivenessService:
    def _normalize_symbols_override(self, symbols: list[str] | None) -> list[str]:
        ...

    def compute_for_exchange(self, db, exchange: str, period: str = "1h", force: bool = False, symbols_override: list[str] | None = None):
        symbols = self._normalize_symbols_override(symbols_override) or self._get_symbols(db, exchange)
        ...
```

Also update any internal call sites needed by the research service so a top-20 symbol set can be evaluated without mutating the user watchlist.

- [ ] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_effectiveness_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the explicit-symbol extension**

```bash
git add backend/services/factor_effectiveness_service.py backend/tests/services/test_factor_effectiveness_service.py
git commit -m "feat: allow factor effectiveness runs for explicit symbols"
```

### Task 4: Add Prescreening, Thresholds, Strategy Generation, And Batch Backtest Logic

**Files:**
- Modify: `backend/services/factor_research_service.py`
- Modify: `backend/tests/services/test_factor_research_service.py`

- [ ] **Step 1: Write the failing tests for factor direction, thresholds, and scheduled-only backtest config**

```python
from services.factor_research_service import (
    map_factor_direction,
    build_percentile_thresholds,
    build_research_backtest_config,
)


def test_map_factor_direction_positive_ic_is_trend_following():
    assert map_factor_direction(ic_value=0.12) == {"high_signal": "long", "low_signal": "short"}


def test_map_factor_direction_negative_ic_is_reversed():
    assert map_factor_direction(ic_value=-0.08) == {"high_signal": "short", "low_signal": "long"}


def test_build_research_backtest_config_is_scheduled_only():
    config = build_research_backtest_config(
        code="print('x')",
        symbols=["BTC", "ETH"],
        start_time_ms=1,
        end_time_ms=2,
    )
    assert config.signal_pool_ids == []
    assert config.scheduled_interval_sec == 3600
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `FAIL` because the orchestration helpers do not exist yet.

- [ ] **Step 3: Implement the research orchestration**

Implement these units inside `factor_research_service.py`:

```python
def map_factor_direction(ic_value: float | None) -> dict[str, str]:
    ...


def build_percentile_thresholds(series: list[float]) -> dict[str, float]:
    # p20 / p50 / p80
    ...


def generate_factor_strategy_code(factor_name: str, period: str, thresholds: dict[str, float], direction: dict[str, str]) -> str:
    # deterministic Program Trader strategy template
    ...


def build_research_backtest_config(...):
    return BacktestConfig(
        code=generated_code,
        signal_pool_ids=[],
        symbols=symbols,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        scheduled_interval_sec=3600,
        ...
    )


class FactorResearchService:
    def run_research(self, ...):
        # resolve universe -> collect factors -> ensure effectiveness -> prescreen
        # -> build thresholds -> engine.run(config) -> score -> rank
        ...
```

The generated strategy code should:

- read `data.get_factor(symbol, factor_name, "1h")`
- open at `P80/P20`
- close toward `P50`
- obey the positive/negative IC direction mapping
- keep execution assumptions fixed across all factors

- [ ] **Step 4: Re-run the targeted unit tests**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the orchestration core**

```bash
git add backend/services/factor_research_service.py backend/tests/services/test_factor_research_service.py
git commit -m "feat: add factor research orchestration and batch backtest logic"
```

### Task 5: Expose The Research Run Through A Thin API Route

**Files:**
- Create: `backend/api/factor_research_routes.py`
- Create: `backend/tests/api/test_factor_research_routes.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing route tests**

```python
from fastapi.testclient import TestClient


def test_factor_research_run_returns_ranked_results(client: TestClient):
    response = client.post("/api/factor-research/run", json={})
    assert response.status_code == 200
    assert "ranked_results" in response.json()
```

- [ ] **Step 2: Run the targeted route tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_factor_research_routes.py -v`

Expected: `FAIL` because the router does not exist yet.

- [ ] **Step 3: Implement the route and wire it into `main.py`**

```python
router = APIRouter(prefix="/api/factor-research", tags=["factor-research"])


class ResearchRunRequest(BaseModel):
    exchange: str = "hyperliquid"
    top_n_symbols: int = 20
    lookback_days: int = 180
    objective: str = "return_over_drawdown"
    factor_scope: str = "builtin_only"


@router.post("/run")
async def run_factor_research(request: ResearchRunRequest, db: Session = Depends(get_db)):
    service = FactorResearchService(db)
    return service.run_research(...)
```

Also add:

```python
from api.factor_research_routes import router as factor_research_router
app.include_router(factor_research_router)
```

- [ ] **Step 4: Re-run the targeted route tests**

Run: `cd backend && uv run pytest tests/api/test_factor_research_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the route**

```bash
git add backend/api/factor_research_routes.py backend/tests/api/test_factor_research_routes.py backend/main.py
git commit -m "feat: expose factor research pipeline route"
```

### Task 6: Add A Small Mocked Integration Test For The End-To-End Pipeline

**Files:**
- Create: `backend/tests/services/test_factor_research_integration.py`
- Modify: `backend/services/factor_research_service.py`

- [ ] **Step 1: Write the failing mocked integration test**

```python
def test_run_research_returns_ranked_results_for_small_fixture(db_session, monkeypatch):
    # 2 symbols, 2 factors, mocked effectiveness, mocked backtest outputs
    ...
    result = FactorResearchService(db_session).run_research(
        exchange="hyperliquid",
        top_n_symbols=2,
        lookback_days=14,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
    )
    assert result["top_factor"]["factor_name"] == "FACTOR_B"
    assert len(result["ranked_results"]) == 2
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run: `cd backend && uv run pytest tests/services/test_factor_research_integration.py -v`

Expected: `FAIL` because at least one orchestration seam is still missing or not injectable enough.

- [ ] **Step 3: Make the smallest glue changes needed for the test to pass**

Typical minimal adjustments:

```python
class FactorResearchService:
    def __init__(self, db, engine_factory=ProgramBacktestEngine):
        self.db = db
        self.engine_factory = engine_factory
```

Use injectable collaborators where tests need deterministic behavior instead of hard-coded network or engine calls.

- [ ] **Step 4: Run the focused suite, then the backend verification suite**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_effectiveness_service.py tests/services/test_factor_research_integration.py tests/api/test_factor_research_routes.py -v`

Expected: `PASS`

Run: `cd backend && uv run pytest -v`

Expected: `PASS` or a clearly understood list of pre-existing failures that are unrelated to this work.

Run: `cd backend && uv run ruff check .`

Expected: no new lint errors from the modified files.

- [ ] **Step 5: Commit the end-to-end testability pass**

```bash
git add backend/services/factor_research_service.py backend/tests/services/test_factor_research_integration.py
git commit -m "test: cover factor research pipeline end to end"
```

### Task 7: Manual Research Run And Formal Verification

**Files:**
- No code changes required unless verification exposes a bug

- [ ] **Step 1: Run a tiny local dry-run directly through Python**

Run:

```powershell
Set-Location backend
@'
from database.connection import SessionLocal
from services.factor_research_service import FactorResearchService

with SessionLocal() as db:
    result = FactorResearchService(db).run_research(
        exchange="hyperliquid",
        top_n_symbols=2,
        lookback_days=14,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
    )
    print(result["top_factor"])
'@ | uv run python -
```

Expected: a small ranked result payload with one `top_factor`.

- [ ] **Step 2: Inspect the dry-run output for obvious invalid behavior**

Check:

- ranked results are non-empty
- score ordering is descending
- `top_factor` includes pnl, drawdown, sharpe, and trade count

- [ ] **Step 3: Run the formal research job**

Run:

```powershell
Set-Location backend
@'
from database.connection import SessionLocal
from services.factor_research_service import FactorResearchService

with SessionLocal() as db:
    result = FactorResearchService(db).run_research(
        exchange="hyperliquid",
        top_n_symbols=20,
        lookback_days=180,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
    )
    print(result["top_factor"])
    print(result["ranked_results"][:10])
'@ | uv run python -
```

Expected: the pipeline completes and prints the top factor plus the top-10 leaderboard.

- [ ] **Step 4: Capture and summarize the winning factor**

Record:

- winning factor name
- return over drawdown score
- total pnl percent
- max drawdown percent
- sharpe ratio
- total trades

- [ ] **Step 5: If verification exposed a bug, return to the relevant TDD task before claiming completion**

Do not mark the work complete if the formal run fails or produces obviously broken rankings.

---

## Local Review Notes

- Existing `POST /api/programs/backtest` is binding-dependent and not suitable as the primary research entrypoint.
- Existing Hyperliquid symbol management stores availability and user watchlist, but not top-volume ranking.
- Existing factor effectiveness logic uses watchlist-oriented symbol discovery, so explicit symbol overrides are required for a top-20 research run.
- Existing backend tooling supports `pytest` and `ruff` via `uv`.
