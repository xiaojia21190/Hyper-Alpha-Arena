# Factor Strategy Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the product around a `Factor Strategy` lifecycle so users can research weighted multi-factor portfolios, confirm one recommended portfolio, validate it with the shared backtest engine, observe it in paper mode, deploy it, and review factor-level contribution.

**Architecture:** Add a new strategy-centric domain layer beside the existing module-first surfaces. Extend the current factor research service from single-factor ranking into multi-factor portfolio candidate generation, persist confirmed strategies and lifecycle runs in dedicated tables, then layer lifecycle APIs and lifecycle-oriented frontend pages on top of the existing backtest, trader, and attribution infrastructure instead of replacing those systems.

**Tech Stack:** FastAPI, SQLAlchemy ORM + migration scripts, existing `backend/services/factor_research_service.py`, existing `backend/backtest/*` engine, existing account/trader runtime tables, React + Vite, existing `frontend/app/lib/api.ts`, `uv`, `pytest`, `pnpm build`

---

## Scope Check

This spec spans backend domain modeling, research orchestration, lifecycle APIs, and frontend information architecture. Those areas are broad, but for v1 they are not independent products. They form one sequential closed loop:

`Research -> Confirm -> Validate -> Paper/Deploy -> Review`

This plan keeps them in one phased document, but each task ends in a working, testable slice.

## File Structure

### New files

- `backend/database/migrations/create_factor_strategy_tables.py`
  - Create strategy-centric persistence for confirmed strategies, research candidates, validation runs, and deployments
- `backend/services/factor_strategy_service.py`
  - Own confirmation, list/detail queries, and strategy snapshot assembly
- `backend/services/factor_strategy_validation_service.py`
  - Convert a confirmed strategy into executable weighted-score program code and run shared backtests
- `backend/services/factor_strategy_deployment_service.py`
  - Create and manage paper/live deployment records while adapting existing account/runtime infrastructure
- `backend/services/factor_strategy_review_service.py`
  - Build review summaries from validation, deployment, and attribution-style data
- `backend/api/factor_strategy_routes.py`
  - Expose confirm/list/detail/validate/deploy/review endpoints for the lifecycle flow
- `backend/tests/services/test_factor_strategy_service.py`
  - Unit tests for confirmation snapshots, strategy listing, and strategy detail assembly
- `backend/tests/services/test_factor_strategy_validation_service.py`
  - Unit tests for weighted factor code generation and validation run persistence
- `backend/tests/services/test_factor_strategy_deployment_service.py`
  - Unit tests for deployment creation/status handling
- `backend/tests/services/test_factor_strategy_review_service.py`
  - Unit tests for review summary aggregation
- `backend/tests/api/test_factor_strategy_routes.py`
  - Route tests for confirm/list/detail/validate/deploy/review contracts
- `frontend/app/components/strategy/StrategiesPage.tsx`
  - Lifecycle page for confirmed strategies and strategy detail summary
- `frontend/app/components/strategy/StrategyRunsPage.tsx`
  - Lifecycle page for validation, paper, and live run history
- `frontend/app/components/strategy/StrategyReviewPage.tsx`
  - Lifecycle page for factor contribution and retrospective analysis

### Modified files

- `backend/database/models.py`
  - Add ORM models for strategy-centric tables
- `backend/services/factor_research_service.py`
  - Extend research outputs from single-factor ranking to factor scorecards, candidate portfolios, and recommendation
- `backend/api/factor_research_routes.py`
  - Return the richer research payload needed by the new Research workspace
- `backend/main.py`
  - Register the new factor strategy router
- `backend/tests/services/test_factor_research_service.py`
  - Expand research tests for portfolio candidate generation and recommendation
- `backend/tests/api/test_factor_research_routes.py`
  - Expand route tests for the richer research payload
- `frontend/app/lib/api.ts`
  - Add lifecycle API types and client functions for research candidates, strategy confirmation, validation, deployment, and review
- `frontend/app/components/factor/FactorLibrary.tsx`
  - Reframe from factor-only page into the Research workspace with candidate portfolios and confirmation
- `frontend/app/main.tsx`
  - Replace module-first page composition with lifecycle-first composition while preserving legacy reuse underneath
- `frontend/app/components/layout/Sidebar.tsx`
  - Replace legacy top-level navigation labels with lifecycle-oriented entries
- `frontend/app/components/analytics/AttributionAnalysis.tsx`
  - Reuse inside the new Review page instead of as the primary top-level analytics destination
- `frontend/app/components/program/ProgramTrader.tsx`
  - Reuse inside validation/runs flows if required, but no longer as the top-level workflow entry point
- `frontend/app/components/trader/TraderManagement.tsx`
  - Reuse inside deployment flows if required, but no longer as the top-level workflow entry point

## Implementation Notes

- Do not replace existing account, program, signal, or trader tables in v1. Add strategy-centric tables beside them and adapt downward.
- Do not add new frontend testing dependencies. This repo has no frontend test runner configured, and new dependencies are out of scope. Use backend contract tests plus `pnpm build` plus manual smoke verification for frontend tasks.
- Do not mutate an already confirmed strategy when a later research run completes. Create new research outputs and new strategy versions instead.
- Keep Hyperliquid-only and built-in-factor-only restrictions in v1. Do not widen scope during implementation.
- Reuse `backend/services/factor_research_service.py` for research orchestration. Do not create a second research engine.
- Reuse the existing backtest engine by generating weighted-score strategy code. Do not fork the backtest engine into a separate factor-strategy implementation.

---

### Task 1: Add Strategy Persistence Models And Confirmation Service Skeleton

**Files:**
- Create: `backend/database/migrations/create_factor_strategy_tables.py`
- Create: `backend/services/factor_strategy_service.py`
- Create: `backend/tests/services/test_factor_strategy_service.py`
- Modify: `backend/database/models.py`

- [ ] **Step 1: Write the failing strategy confirmation tests**

```python
from services.factor_strategy_service import FactorStrategyService


def test_confirm_strategy_freezes_candidate_snapshot():
    db = DummyDb()
    service = FactorStrategyService(db)

    strategy = service.confirm_candidate(
        research_run_id=7,
        candidate={
            "id": 11,
            "name": "score_weighted_top3",
            "score": 2.8,
            "weights": [
                {"factor_name": "RSI14", "direction": "long_short", "weight": 0.5},
                {"factor_name": "ATR_RATIO", "direction": "short_long", "weight": 0.3},
                {"factor_name": "VOL_Z", "direction": "long_short", "weight": 0.2},
            ],
            "rationale": {"summary": "best balance of coverage and drawdown"},
        },
        exchange="hyperliquid",
        period="1h",
    )

    assert strategy["source_candidate_id"] == 11
    assert len(strategy["components"]) == 3
    assert strategy["components"][0]["factor_name"] == "RSI14"


def test_list_strategies_returns_latest_versions_first():
    db = DummyDb.with_strategies([
        {"id": 1, "name": "alpha-a", "version": 1},
        {"id": 2, "name": "alpha-b", "version": 3},
    ])
    rows = FactorStrategyService(db).list_strategies()
    assert [row["id"] for row in rows] == [2, 1]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_service.py -v`

Expected: `FAIL` because the strategy service and strategy persistence models do not exist yet.

- [ ] **Step 3: Add the ORM models, migration, and minimal confirmation service**

```python
class FactorStrategy(Base):
    __tablename__ = "factor_strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    exchange = Column(String(20), nullable=False, default="hyperliquid")
    period = Column(String(10), nullable=False, default="1h")
    version = Column(Integer, nullable=False, default=1)
    source_research_run_id = Column(Integer, nullable=True, index=True)
    source_candidate_id = Column(Integer, nullable=True, index=True)
    recommended_at_confirmation = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="draft")


class FactorStrategyComponent(Base):
    __tablename__ = "factor_strategy_components"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("factor_strategies.id"), nullable=False, index=True)
    factor_name = Column(String(100), nullable=False)
    direction = Column(String(30), nullable=False)
    weight = Column(Float, nullable=False)


class FactorStrategyService:
    def confirm_candidate(self, research_run_id: int, candidate: dict, exchange: str, period: str) -> dict:
        ...
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_service.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the persistence baseline**

```bash
git add backend/database/models.py backend/database/migrations/create_factor_strategy_tables.py backend/services/factor_strategy_service.py backend/tests/services/test_factor_strategy_service.py
git commit -m "feat: add factor strategy persistence foundation"
```

### Task 2: Extend Research Output From Single-Factor Ranking To Portfolio Candidates

**Files:**
- Modify: `backend/services/factor_research_service.py`
- Modify: `backend/api/factor_research_routes.py`
- Modify: `backend/tests/services/test_factor_research_service.py`
- Modify: `backend/tests/api/test_factor_research_routes.py`

- [ ] **Step 1: Write the failing research tests for portfolio candidate generation and recommendation**

```python
from services.factor_research_service import (
    build_portfolio_candidates,
    recommend_portfolio_candidate,
)


def test_build_portfolio_candidates_returns_score_weighted_and_balanced_variants():
    candidates = build_portfolio_candidates([
        {"factor_name": "RSI14", "research_score": 0.95, "category": "momentum"},
        {"factor_name": "ATR_RATIO", "research_score": 0.90, "category": "volatility"},
        {"factor_name": "VOL_Z", "research_score": 0.85, "category": "volume"},
    ])

    methods = {row["construction_method"] for row in candidates}
    assert "score_weighted_top_n" in methods
    assert "category_balanced_weighted" in methods


def test_recommend_portfolio_candidate_prefers_best_score_with_rationale():
    recommended = recommend_portfolio_candidate([
        {"id": 1, "score": 1.9, "construction_method": "equal_weight"},
        {"id": 2, "score": 2.4, "construction_method": "score_weighted_top_n"},
    ])

    assert recommended["id"] == 2
    assert "rationale" in recommended
```

- [ ] **Step 2: Run the targeted research tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/api/test_factor_research_routes.py -v`

Expected: `FAIL` because the service still emits single-factor results only.

- [ ] **Step 3: Implement factor scorecards, portfolio candidates, and recommended candidate output**

```python
def build_portfolio_candidates(rows: list[dict]) -> list[dict]:
    top_rows = rows[:5]
    return [
        build_equal_weight_candidate(top_rows),
        build_score_weighted_candidate(top_rows),
        build_category_balanced_candidate(top_rows),
    ]


def recommend_portfolio_candidate(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    best = sorted(candidates, key=lambda row: row["score"], reverse=True)[0]
    return {
        **best,
        "rationale": {
            "summary": "highest composite score with acceptable balance",
        },
    }


result = {
    "factor_scorecard": factor_scorecard,
    "portfolio_candidates": portfolio_candidates,
    "recommended_portfolio": recommended_portfolio,
    ...
}
```

- [ ] **Step 4: Re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/api/test_factor_research_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the richer research contract**

```bash
git add backend/services/factor_research_service.py backend/api/factor_research_routes.py backend/tests/services/test_factor_research_service.py backend/tests/api/test_factor_research_routes.py
git commit -m "feat: add portfolio candidates to factor research"
```

### Task 3: Add Factor Strategy Lifecycle Routes For Confirm/List/Detail

**Files:**
- Create: `backend/api/factor_strategy_routes.py`
- Create: `backend/tests/api/test_factor_strategy_routes.py`
- Modify: `backend/services/factor_strategy_service.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write the failing route tests for confirm/list/detail**

```python
def test_confirm_factor_strategy_returns_created_snapshot():
    response = client.post("/api/factor-strategies/confirm", json={
        "research_run_id": 7,
        "candidate_id": 11,
        "name": "HL Score Weighted v1",
    })

    assert response.status_code == 201
    assert response.json()["strategy"]["name"] == "HL Score Weighted v1"


def test_list_factor_strategies_returns_summary_rows():
    response = client.get("/api/factor-strategies")
    assert response.status_code == 200
    assert "items" in response.json()
```

- [ ] **Step 2: Run the targeted route tests to verify they fail**

Run: `cd backend && uv run pytest tests/api/test_factor_strategy_routes.py -v`

Expected: `FAIL` because the router is not registered yet.

- [ ] **Step 3: Implement the lifecycle router and register it**

```python
router = APIRouter(prefix="/api/factor-strategies", tags=["factor-strategies"])


@router.post("/confirm", status_code=201)
def confirm_factor_strategy(payload: ConfirmFactorStrategyRequest, db: Session = Depends(get_db)):
    service = FactorStrategyService(db)
    return {"strategy": service.confirm_candidate_by_id(...)}


@router.get("")
def list_factor_strategies(db: Session = Depends(get_db)):
    return {"items": FactorStrategyService(db).list_strategies()}


@router.get("/{strategy_id}")
def get_factor_strategy(strategy_id: int, db: Session = Depends(get_db)):
    return {"strategy": FactorStrategyService(db).get_strategy_detail(strategy_id)}
```

- [ ] **Step 4: Re-run the targeted route tests**

Run: `cd backend && uv run pytest tests/api/test_factor_strategy_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the strategy lifecycle API baseline**

```bash
git add backend/api/factor_strategy_routes.py backend/services/factor_strategy_service.py backend/tests/api/test_factor_strategy_routes.py backend/main.py
git commit -m "feat: add factor strategy lifecycle routes"
```

### Task 4: Add Validation Runs On Top Of The Shared Backtest Engine

**Files:**
- Create: `backend/services/factor_strategy_validation_service.py`
- Create: `backend/tests/services/test_factor_strategy_validation_service.py`
- Modify: `backend/api/factor_strategy_routes.py`
- Modify: `backend/services/factor_strategy_service.py`

- [ ] **Step 1: Write the failing validation tests for weighted-score code generation and persistence**

```python
from services.factor_strategy_validation_service import (
    build_weighted_factor_strategy_code,
    FactorStrategyValidationService,
)


def test_build_weighted_factor_strategy_code_embeds_weighted_factor_score():
    code = build_weighted_factor_strategy_code(
        components=[
            {"factor_name": "RSI14", "weight": 0.6, "direction": "long_short"},
            {"factor_name": "ATR_RATIO", "weight": 0.4, "direction": "short_long"},
        ],
        period="1h",
        symbols=["BTC", "ETH"],
    )

    assert 'weighted_score += 0.6' in code
    assert 'data.get_factor(symbol, "RSI14", period="1h")' in code
    assert 'data.get_factor(symbol, "ATR_RATIO", period="1h")' in code


def test_run_validation_persists_metrics_snapshot():
    result = FactorStrategyValidationService(DummyDb(), DummyBacktestEngine()).run_validation(strategy_id=3)
    assert result["status"] == "success"
    assert result["metrics"]["total_pnl_percent"] == 12.5
```

- [ ] **Step 2: Run the targeted validation tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_validation_service.py -v`

Expected: `FAIL` because no validation service exists yet.

- [ ] **Step 3: Implement the validation service and route**

```python
def build_weighted_factor_strategy_code(components: list[dict], period: str, symbols: list[str]) -> str:
    return """
class WeightedFactorStrategy:
    def should_trade(self, data):
        weighted_score = 0.0
        ...
"""


@router.post("/{strategy_id}/validate", status_code=202)
def validate_factor_strategy(strategy_id: int, db: Session = Depends(get_db)):
    return FactorStrategyValidationService(db).run_validation(strategy_id)
```

- [ ] **Step 4: Re-run the targeted validation tests and route tests**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_validation_service.py tests/api/test_factor_strategy_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the validation run slice**

```bash
git add backend/services/factor_strategy_validation_service.py backend/tests/services/test_factor_strategy_validation_service.py backend/api/factor_strategy_routes.py backend/services/factor_strategy_service.py
git commit -m "feat: add factor strategy validation runs"
```

### Task 5: Add Deployment And Review Facades Without Replacing Existing Runtime Systems

**Files:**
- Create: `backend/services/factor_strategy_deployment_service.py`
- Create: `backend/services/factor_strategy_review_service.py`
- Create: `backend/tests/services/test_factor_strategy_deployment_service.py`
- Create: `backend/tests/services/test_factor_strategy_review_service.py`
- Modify: `backend/api/factor_strategy_routes.py`

- [ ] **Step 1: Write the failing tests for deployment records and review summaries**

```python
def test_create_paper_deployment_records_mode_and_account():
    deployment = FactorStrategyDeploymentService(DummyDb()).create_deployment(
        strategy_id=3,
        account_id=9,
        mode="paper",
        environment="mainnet",
    )

    assert deployment["mode"] == "paper"
    assert deployment["account_id"] == 9


def test_build_review_summary_groups_factor_contribution():
    review = FactorStrategyReviewService(DummyDb()).build_review_summary(strategy_id=3)
    assert "factor_contribution" in review
    assert review["factor_contribution"][0]["factor_name"] == "RSI14"
```

- [ ] **Step 2: Run the targeted deployment/review tests to verify they fail**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_deployment_service.py tests/services/test_factor_strategy_review_service.py -v`

Expected: `FAIL` because deployment and review services do not exist yet.

- [ ] **Step 3: Implement the deployment facade and review summary service**

```python
class FactorStrategyDeploymentService:
    def create_deployment(self, strategy_id: int, account_id: int, mode: str, environment: str) -> dict:
        # create strategy_deployment row and adapt existing runtime hooks later
        ...


class FactorStrategyReviewService:
    def build_review_summary(self, strategy_id: int) -> dict:
        return {
            "strategy_id": strategy_id,
            "factor_contribution": [...],
            "validation_summary": {...},
            "deployment_summary": {...},
        }
```

- [ ] **Step 4: Add routes and re-run the targeted tests**

Run: `cd backend && uv run pytest tests/services/test_factor_strategy_deployment_service.py tests/services/test_factor_strategy_review_service.py tests/api/test_factor_strategy_routes.py -v`

Expected: `PASS`

- [ ] **Step 5: Commit the deployment/review facade layer**

```bash
git add backend/services/factor_strategy_deployment_service.py backend/services/factor_strategy_review_service.py backend/tests/services/test_factor_strategy_deployment_service.py backend/tests/services/test_factor_strategy_review_service.py backend/api/factor_strategy_routes.py
git commit -m "feat: add factor strategy deployment and review services"
```

### Task 6: Rebuild The Research Page Into A Research Workspace With Candidate Confirmation

**Files:**
- Modify: `frontend/app/components/factor/FactorLibrary.tsx`
- Modify: `frontend/app/lib/api.ts`
- Modify: `backend/tests/api/test_factor_research_routes.py`
- Modify: `backend/tests/api/test_factor_strategy_routes.py`

- [ ] **Step 1: Lock the backend contracts the new Research workspace depends on**

```python
def test_factor_research_status_includes_portfolio_candidates_and_recommendation():
    response = client.get("/api/factor-research/status")
    assert response.status_code == 200
    payload = response.json()
    assert "last_result" in payload
    assert "portfolio_candidates" in payload["last_result"]
    assert "recommended_portfolio" in payload["last_result"]
```

- [ ] **Step 2: Run the targeted API contract tests**

Run: `cd backend && uv run pytest tests/api/test_factor_research_routes.py tests/api/test_factor_strategy_routes.py -v`

Expected: `PASS` before frontend work begins, so the UI is built against stable contracts.

- [ ] **Step 3: Implement the frontend Research workspace state and confirmation flow**

```ts
export interface ResearchPortfolioCandidate {
  id: number
  name: string
  score: number
  construction_method: string
  weights: Array<{ factor_name: string; direction: string; weight: number }>
  rationale: { summary: string }
}

export async function confirmFactorStrategy(payload: ConfirmFactorStrategyRequest) {
  const response = await apiRequest("/factor-strategies/confirm", {
    method: "POST",
    body: JSON.stringify(payload),
  })
  return response.json()
}
```

```tsx
const recommendedCandidate = researchStatus?.last_result?.recommended_portfolio
const portfolioCandidates = researchStatus?.last_result?.portfolio_candidates || []
```

- [ ] **Step 4: Run the frontend build to verify the page compiles**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [ ] **Step 5: Commit the Research workspace flow**

```bash
git add frontend/app/components/factor/FactorLibrary.tsx frontend/app/lib/api.ts backend/tests/api/test_factor_research_routes.py backend/tests/api/test_factor_strategy_routes.py
git commit -m "feat: add research workspace strategy confirmation flow"
```

### Task 7: Add Lifecycle Pages For Strategies, Runs, And Review And Reframe Navigation

**Files:**
- Create: `frontend/app/components/strategy/StrategiesPage.tsx`
- Create: `frontend/app/components/strategy/StrategyRunsPage.tsx`
- Create: `frontend/app/components/strategy/StrategyReviewPage.tsx`
- Modify: `frontend/app/main.tsx`
- Modify: `frontend/app/components/layout/Sidebar.tsx`
- Modify: `frontend/app/lib/api.ts`
- Modify: `frontend/app/components/analytics/AttributionAnalysis.tsx`

- [ ] **Step 1: Create the lifecycle page shells and wire them into navigation**

```tsx
{currentPage === "strategies" && <StrategiesPage />}
{currentPage === "runs" && <StrategyRunsPage />}
{currentPage === "review" && <StrategyReviewPage />}
```

```tsx
const desktopNav = [
  { label: "Research", page: "factor-library", icon: FlaskConical },
  { label: "Strategies", page: "strategies", icon: Ghost },
  { label: "Runs", page: "runs", icon: ScrollText },
  { label: "Review", page: "review", icon: AttributionIcon },
  { label: "System", page: "settings", icon: Settings },
]
```

- [ ] **Step 2: Run the frontend build to verify the shell wiring fails in a focused way**

Run: `cd frontend && pnpm build`

Expected: `FAIL` until the new page components and API bindings are fully implemented.

- [ ] **Step 3: Implement the lifecycle pages by adapting existing module views under lifecycle labels**

```tsx
export default function StrategiesPage() {
  const [items, setItems] = useState<FactorStrategySummary[]>([])
  ...
}

export default function StrategyRunsPage() {
  // render validation and deployment history from lifecycle APIs
}

export default function StrategyReviewPage() {
  // render factor contribution, validation summary, and review notes
}
```

- [ ] **Step 4: Re-run the frontend build**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [ ] **Step 5: Commit the lifecycle-first frontend**

```bash
git add frontend/app/components/strategy/StrategiesPage.tsx frontend/app/components/strategy/StrategyRunsPage.tsx frontend/app/components/strategy/StrategyReviewPage.tsx frontend/app/main.tsx frontend/app/components/layout/Sidebar.tsx frontend/app/lib/api.ts frontend/app/components/analytics/AttributionAnalysis.tsx
git commit -m "feat: add lifecycle-first factor strategy navigation"
```

### Task 8: Run Regression Checks And Update User-Facing Docs

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/superpowers/specs/2026-03-21-factor-strategy-platform-design.md`

- [ ] **Step 1: Update the documentation to reflect the lifecycle-first platform**

```md
- Research: build and compare weighted factor portfolios
- Strategies: manage confirmed factor strategies
- Runs: validate and deploy strategies
- Review: inspect factor contribution and retrospective analysis
```

- [ ] **Step 2: Run the backend targeted regression suite**

Run: `cd backend && uv run pytest tests/services/test_factor_research_service.py tests/services/test_factor_strategy_service.py tests/services/test_factor_strategy_validation_service.py tests/services/test_factor_strategy_deployment_service.py tests/services/test_factor_strategy_review_service.py tests/api/test_factor_research_routes.py tests/api/test_factor_strategy_routes.py -v`

Expected: `PASS`

- [ ] **Step 3: Run the frontend regression gate**

Run: `cd frontend && pnpm build`

Expected: `PASS`

- [ ] **Step 4: Run the final app import smoke check on the supported runtime**

Run: `cd backend && uv run python -c "import main; print('import-ok')"`

Expected: `PASS` on the supported Python/runtime baseline for this repository. If the local machine still uses an unsupported environment, run this check in the repository's supported Python 3.12 path before claiming completion.

- [ ] **Step 5: Commit the documented, verified lifecycle platform**

```bash
git add README.md README.zh-CN.md docs/superpowers/specs/2026-03-21-factor-strategy-platform-design.md
git commit -m "docs: update factor strategy platform workflow"
```
