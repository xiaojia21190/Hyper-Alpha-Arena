# Factor Strategy Platform Design

**Date:** 2026-03-21

## Goal

Reorient the product from a collection of parallel trading modules into a factor-driven platform centered on one primary workflow:

`Research -> Validate -> Paper -> Deploy -> Review`

The first version should let a user:

1. research multiple built-in factors,
2. generate weighted multi-factor portfolio candidates,
3. review a system recommendation,
4. manually confirm one portfolio,
5. run backtests on that confirmed portfolio,
6. observe it in paper trading,
7. deploy it to live trading,
8. review factor-level contribution and decide whether to iterate.

This is a product-flow redesign, not only a new factor-research screen.

## Confirmed Scope

- Core object: `Factor Strategy`
- Strategy type: fixed-weight multi-factor scoring strategy
- Weight source: system-derived from historical factor effectiveness and research score
- Recommendation model: candidate leaderboard plus one recommended portfolio
- Confirmation model: human must confirm before the portfolio becomes an executable strategy
- Exchange scope for v1: `hyperliquid`
- Factor scope for v1: built-in factors only
- Promotion policy: no automatic promotion from research to validation, paper, or live

## Why This Direction

The repository already has strong building blocks, but they are presented as parallel modules:

- factor library and factor effectiveness
- Program Trader and shared backtest engine
- signal system
- AI Trader and deployment/runtime infrastructure
- attribution analytics

That structure makes users assemble the workflow themselves.

The redesign should preserve those underlying capabilities while changing the product mental model. Users should no longer think in terms of "go to Factor, then Program, then Signal, then Attribution." They should think in terms of advancing one factor strategy through lifecycle stages.

## Product Thesis

The product should become a factor strategy platform, not just a factor library with extra tools attached.

The key shift is:

- today: modules are first-class, workflow is implicit
- target: workflow is first-class, modules become supporting capabilities

In v1, the platform should optimize for one trusted closed loop:

`multi-factor research -> recommendation -> confirmation -> backtest -> paper -> live -> review`

## Core Object Model

### Factor Strategy

`Factor Strategy` becomes the main user-facing asset.

A factor strategy is a manually confirmed, fixed-weight multi-factor portfolio definition that carries:

- factor list
- factor directions
- factor weights
- research snapshot
- recommendation snapshot
- validation history
- paper/live deployment state
- review history

Every downstream phase should reference the strategy object instead of rebuilding intent from separate prompt, program, signal, and trader objects.

### Supporting Lifecycle Objects

The platform should add lifecycle objects around the core strategy:

- `Research Run`
- `Research Portfolio Candidate`
- `Strategy Validation Run`
- `Strategy Deployment`
- `Strategy Review Snapshot`

This separation keeps research, validation, and runtime concerns distinct and prevents one failed phase from corrupting another.

## User Workflow

### 1. Research

Research should produce three result layers:

1. `Factor Scorecard`
2. `Candidate Portfolio Leaderboard`
3. `Recommended Portfolio`

#### Factor Scorecard

Each factor should be scored with normalized metrics such as:

- IC
- ICIR
- coverage
- stability
- return-over-drawdown style research score
- direction hint

The goal is not to pick one winning factor directly. The goal is to identify which factors deserve entry into the candidate portfolio pool.

#### Candidate Portfolio Leaderboard

The system should generate a small set of candidate portfolios from high-quality factors.

V1 candidate construction should stay simple and deterministic. Good first-pass portfolio templates are:

- top-N equal weight portfolio
- score-weighted portfolio
- category-balanced score-weighted portfolio

V1 should avoid complex optimizer-driven search.

#### Recommended Portfolio

The system should choose one candidate as the recommendation and explain why:

- why it outranks the others
- which factors contribute most
- what the main risk tradeoff is
- why it is suitable for promotion to validation

This explanation is part of the product, not optional polish. Users need to understand why the system recommends one portfolio over another.

### 2. Confirm

Research output should not become executable automatically.

The user must explicitly confirm one candidate portfolio. Confirmation freezes a snapshot into a `Factor Strategy`:

- component factors
- weights
- directions
- research metrics snapshot
- recommendation rationale snapshot
- run configuration snapshot

Freezing this snapshot is necessary so later validation, paper, live, and review phases all refer to the same versioned definition.

### 3. Validate

Validation should compile the confirmed strategy into one shared execution form and run it through the existing backtest engine.

Program Trader should remain the underlying execution substrate, but it should no longer be the primary product concept.

Validation should output at least:

- total return
- max drawdown
- Sharpe
- trade count
- turnover
- win rate
- performance by symbol
- performance by market regime segment

### 4. Paper

Paper trading should run the confirmed strategy in simulated mode using existing runtime/account infrastructure.

Users should not need to think in terms of creating a separate trader object from scratch. They should deploy a factor strategy into paper mode.

### 5. Deploy

Live deployment should bind a validated strategy to:

- account
- exchange environment
- leverage/risk settings
- activation status
- runtime version

Existing account and trader infrastructure can be reused underneath, but the product surface should present this as strategy deployment.

### 6. Review

Review should answer:

- which factors contributed positively
- which factors dragged performance
- which market conditions helped or hurt the strategy
- whether a new research cycle is warranted

Attribution should evolve from a standalone analytics screen into the review phase of the factor strategy lifecycle.

## Information Architecture

The current product presents many peer-level pages. The redesign should shift navigation toward lifecycle stages.

Recommended v1 top-level navigation:

- `Research`
- `Strategies`
- `Runs`
- `Review`
- `System`

Interpretation:

- `Research` owns scorecards, candidate portfolios, and recommendation
- `Strategies` owns confirmed strategy definitions and versions
- `Runs` owns validation, paper, and live activity
- `Review` owns factor contribution and strategy retrospective analysis
- `System` keeps infrastructure setup, accounts, exchange config, logs, and support tools

## Existing Module Mapping

Existing capabilities should be preserved but repositioned.

### Factor Library

Current factor library UI should evolve into the `Research Workspace`.

### Program Trader

Program Trader should remain as a backtest and execution engine, but product-facing language should stop making users treat it as a separate destination for primary workflow.

### Signal System

Signals should become a trigger/risk layer attached to strategies rather than a parallel product track.

### AI Trader

AI Trader should no longer be the main workflow entry for this platform direction. If retained, it should play a supporting role such as:

- explaining recommendations,
- summarizing validation outcomes,
- assisting review and diagnosis.

### Attribution

Attribution should become the `Review` center for factor strategies.

## Data Model

V1 should introduce dedicated data structures instead of overloading unrelated legacy tables.

### `factor_strategy`

Represents a manually confirmed factor portfolio strategy.

Suggested fields:

- `id`
- `name`
- `description`
- `exchange`
- `period`
- `status`
- `version`
- `source_research_run_id`
- `source_candidate_id`
- `recommended_at_confirmation`
- `risk_config_json`
- `created_at`
- `confirmed_at`
- `archived_at`

### `factor_strategy_component`

Represents one factor inside a strategy.

Suggested fields:

- `id`
- `strategy_id`
- `factor_name`
- `direction`
- `weight`
- `ordinal`
- `is_enabled`
- `research_score_snapshot`
- `metadata_json`

### `research_run`

Represents one full multi-factor research execution.

Suggested fields:

- `id`
- `exchange`
- `period`
- `lookback_days`
- `factor_scope`
- `status`
- `config_json`
- `factor_candidate_count`
- `portfolio_candidate_count`
- `recommended_candidate_id`
- `error_message`
- `started_at`
- `completed_at`

### `research_portfolio_candidate`

Represents one candidate portfolio produced by a research run.

Suggested fields:

- `id`
- `research_run_id`
- `name`
- `rank`
- `score`
- `is_recommended`
- `selection_status`
- `construction_method`
- `weights_json`
- `rationale_json`
- `metrics_json`

### `strategy_validation_run`

Represents one backtest/validation run for a confirmed strategy.

Suggested fields:

- `id`
- `strategy_id`
- `version`
- `status`
- `config_json`
- `metrics_json`
- `started_at`
- `completed_at`
- `error_message`

### `strategy_deployment`

Represents one paper or live deployment.

Suggested fields:

- `id`
- `strategy_id`
- `version`
- `account_id`
- `mode`
- `environment`
- `status`
- `runtime_config_json`
- `last_error`
- `started_at`
- `stopped_at`

## Strategy Construction Rules

V1 strategy construction should stay constrained:

- built-in factors only
- Hyperliquid only
- fixed weights after confirmation
- system-derived weights from historical research score
- deterministic candidate generation rules
- one recommended portfolio per run
- one manually selected portfolio promoted forward

V1 should not include:

- online dynamic weight updates
- auto-promotion to live
- optimizer-heavy weight search
- ML-based portfolio fitting
- auto-rebalancing research models
- full cross-exchange portfolio design

## Migration Strategy

The redesign should be incremental, not destructive.

### Phase 1

- add new strategy-centric tables and APIs
- keep current legacy modules intact
- implement the new research and strategy flow beside existing navigation

### Phase 2

- reframe navigation around lifecycle stages
- reduce emphasis on old module-first entry points
- adapt legacy execution/runtime services to strategy-oriented surfaces

### Phase 3

- remove or hide redundant module-first flows once the new strategy flow is stable

This staged approach avoids breaking the current system while product direction changes.

## Error Handling Principles

Failure states must remain phase-local.

### Research failure

If factor scoring or portfolio candidate generation fails, preserve the `research_run` record with clear failure state. Do not create a strategy.

### Validation failure

If backtest compilation or execution fails, preserve the strategy and create a failed `strategy_validation_run`.

### Paper/live deployment failure

If runtime, market-data, account, or exchange operations fail, preserve the strategy and mark the deployment as failed or degraded without invalidating the research and validation lineage.

### Version stability

Confirmed strategies must be versioned snapshots. A later research rerun must not silently mutate an already validated or deployed strategy.

## Testing Strategy

### Unit tests

Add tests for:

- factor score normalization
- candidate portfolio generation
- strategy recommendation ranking
- confirmation snapshot creation
- weight and direction persistence

### Integration tests

Add tests for:

- research run producing factor scorecards and portfolio candidates
- selecting one recommended or non-recommended portfolio
- converting the selection into a strategy
- running one validation pass on that strategy

### UI workflow tests

At minimum, verify:

- research workspace renders candidate portfolios and recommendation
- user can confirm a candidate into a strategy
- strategy appears in validation, paper, deploy, and review entry points

### Manual verification

Before implementation is considered complete, verify the end-to-end happy path:

1. run research
2. inspect leaderboard and recommendation
3. confirm one strategy
4. run validation
5. start paper deployment
6. inspect review output

## Risks

### Product complexity risk

If candidate generation, weighting, and review logic become too sophisticated in v1, the platform will become hard to trust and hard to debug.

### Data consistency risk

If research outputs are not frozen at confirmation time, downstream stages will drift and auditability will collapse.

### Migration risk

If legacy module-first navigation remains dominant while the new flow is only partially added, the product will become more confusing instead of less.

### Overfitting risk

System-derived weights from one historical window can still overfit. V1 should frame the recommendation as decision support, not statistical certainty.

## Implementation Direction

Implementation should prioritize:

1. introducing the `Factor Strategy` object and lifecycle records,
2. extending research from single-factor ranking to multi-factor candidate portfolios,
3. reusing existing backtest and runtime systems instead of replacing them,
4. surfacing one clear lifecycle-oriented UI flow,
5. preserving manual confirmation gates before promotion.

## Non-Goals

The first version does not attempt to:

- replace the entire execution stack,
- discover optimal weights through unconstrained search,
- make live trading fully autonomous,
- support cross-exchange portfolio research,
- solve every current module overlap immediately.

The target is a credible and understandable first-pass factor strategy platform with one strong closed loop.
