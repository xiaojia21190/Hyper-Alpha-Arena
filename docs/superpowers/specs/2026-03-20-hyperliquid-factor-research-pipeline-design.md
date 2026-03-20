# Hyperliquid Factor Research Pipeline Design

**Date:** 2026-03-20

## Goal

Build a first-pass research pipeline inside the existing system that:

1. selects the top 20 Hyperliquid symbols by trading volume,
2. evaluates built-in factors over the last 180 days,
3. batch-backtests those factors under one shared Program Trader template,
4. ranks results by `total_return / max_drawdown`,
5. returns the best-performing factor with comparable evidence.

This pipeline is intended to produce a working research-to-backtest loop, not a full multi-factor portfolio research platform.

## Confirmed Scope

- Exchange: `hyperliquid`
- Universe: top 20 symbols by volume
- Lookback window: `180` days
- Factor scope: built-in only
- Final objective: optimize `return_over_drawdown`

For this repository, "built-in only" means:

- factors from `services.factor_registry.FACTOR_REGISTRY`
- factors stored in `custom_factors` with `source = 'builtin_expression'`

User-created custom factors are excluded from the first version.

## Why This Approach

The repository already contains:

- a factor registry and expression-engine factor system,
- factor effectiveness computation and storage,
- a Program Trader event-driven backtest engine,
- exchange-aware historical data loading for backtests.

The lowest-risk implementation is to add a thin orchestration layer that reuses those pieces instead of building a second research stack.

## Product Outcome

The system should expose one research run that outputs:

- selected universe symbols,
- candidate factors considered,
- prefiltered factors forwarded to backtest,
- per-factor backtest metrics,
- ranked final leaderboard,
- the top factor and its supporting metrics.

The first version may be backend-only. A dedicated frontend page is out of scope.

## Core Design Decisions

### 1. Two-stage selection

The pipeline uses two stages:

1. factor prescreening via effectiveness metrics,
2. batch backtesting via one shared strategy template.

This keeps obviously weak factors out of the expensive batch-backtest phase while still making the final decision from actual backtest performance instead of IC/ICIR alone.

### 2. One shared strategy template

All candidate factors must be evaluated under the same trading logic so the comparison remains about factor quality rather than strategy tuning.

Only these values may differ per factor:

- factor name,
- signal direction mapping,
- threshold values derived from that factor's distribution.

Everything else stays fixed.

### 3. Scheduled triggers, not signal pools

The first version should use scheduled `1h` trigger execution and should not depend on existing signal pools. This removes an unnecessary layer and makes factor comparison deterministic.

### 4. Final ranking by return over drawdown

The final score is:

`score = total_pnl_percent / max(max_drawdown_percent, floor_value)`

Where `floor_value` prevents division by zero and suppresses unrealistic scores from near-zero drawdown runs.

Suggested first-pass floor:

- `floor_value = 1.0`

Tie-breakers:

1. higher `sharpe_ratio`
2. higher `total_pnl_percent`
3. higher `total_trades`

## Candidate Factor Definition

The candidate set is the union of:

- built-in registry factors,
- builtin expression factors inserted into `custom_factors`.

This matches the repository's current split implementation where some built-ins live in the registry and others are shipped as expression-backed factors.

Each candidate factor must carry enough metadata for orchestration:

- factor name,
- source type,
- category,
- whether it is strategy-callable through `data.get_factor(...)`,
- latest effectiveness metrics if available.

## Prefilter Rules

The prefilter stage should run on the confirmed universe and should discard factors that do not meet baseline quality and coverage requirements.

First-pass rules:

- period: `1h`
- primary forward period for screening: `4h`
- require non-null effectiveness record
- require minimum sample count above a configurable threshold
- reject factors with weak coverage across the selected universe
- reject factors with clearly unusable metrics, such as near-zero or strongly unstable effectiveness

This stage is not the final selector. It is only a guardrail to reduce batch size.

## Shared Strategy Template

All backtests use one factor-driven Program Trader strategy template.

### Trigger cadence

- scheduled trigger only
- cadence: `1h`

### Inputs read each cycle

- current factor value for the symbol and period
- cached or precomputed factor percentile thresholds
- factor sign interpretation from effectiveness

### Direction mapping

- if latest factor `IC` is positive:
  - high percentile means long bias
  - low percentile means short bias
- if latest factor `IC` is negative:
  - high percentile means short bias
  - low percentile means long bias

### Initial thresholds

- open long/short at `P80` or `P20`
- close when factor mean-reverts toward `P50`

These thresholds are intentionally fixed in v1 for comparability.

### Uniform execution assumptions

- same initial balance for every factor
- same slippage
- same fee rate
- same leverage policy
- same maximum open position rules
- same position sizing logic

## Architecture

Add one orchestration layer on top of existing services.

### New responsibilities

1. resolve the Hyperliquid top-20 universe,
2. collect built-in candidate factors,
3. ensure factor effectiveness exists for the requested scope,
4. prescreen factors,
5. generate or execute the shared backtest template for each factor,
6. aggregate results and compute the final ranking.

### Existing services to reuse

- factor effectiveness computation service
- factor library data sources
- Program Trader backtest engine
- historical data provider

The new layer should coordinate existing behavior, not duplicate it.

## Data Flow

1. User starts a research run with fixed config.
2. System resolves top 20 Hyperliquid symbols by volume.
3. System loads built-in candidate factors.
4. System computes or refreshes factor effectiveness if required.
5. System prescreens factors using effectiveness summaries.
6. System batch-runs the shared Program Trader backtest for each surviving factor.
7. System computes `return_over_drawdown` score.
8. System stores and returns the ranked results.

## Output Contract

Each completed research run should return:

- run configuration,
- universe symbols,
- candidate factor count,
- prescreened factor count,
- ranked results list,
- top factor summary.

Each factor result should include:

- factor name,
- category,
- source,
- total pnl percent,
- max drawdown percent,
- sharpe ratio,
- win rate,
- trade count,
- final score.

## Error Handling

The pipeline should fail clearly when:

- the universe cannot be resolved,
- too few symbols have usable market data,
- factor effectiveness cannot be produced,
- no factors pass prescreen,
- all batch backtests fail.

Partial failure is acceptable for individual factors. One bad factor should not abort the full run unless the remaining valid sample becomes too small to rank meaningfully.

## Testing Strategy

### Unit coverage

Add tests for:

- universe selection logic,
- built-in factor discovery,
- prescreen filtering,
- final score calculation and tie-breakers,
- result ranking stability.

### Integration coverage

Add a small-scope integration test that uses:

- 2 to 3 symbols,
- a short lookback window,
- a small factor subset,
- the full research orchestration path.

This test should prove the end-to-end pipeline runs and produces ranked results.

### Manual verification

After implementation:

1. run the small integration dataset locally,
2. run the formal research job:
   - exchange `hyperliquid`
   - top 20 symbols
   - 180 days
   - built-in factors only
3. inspect the top-ranked result for metric sanity before declaring success.

## Non-Goals

The first version does not include:

- a rich frontend workflow,
- multi-factor combination search,
- parameter sweeps,
- cross-sectional long-short portfolio construction,
- neutralization and factor orthogonalization,
- user-created factor optimization,
- distributed execution.

## Risks

### Data sufficiency risk

Some top-volume symbols may still have incomplete historical coverage. The pipeline must either exclude them with clear reporting or backfill enough data before scoring.

### Comparability risk

If the strategy template changes between factors, the ranking becomes meaningless. The template and execution assumptions must remain fixed across the batch.

### Overfitting risk

Even with shared logic, selecting a factor from one 180-day window can overfit recent market structure. The first version should be framed as a ranking run, not a statistically final answer.

## Implementation Direction

The implementation should prioritize:

1. backend-only orchestration,
2. smallest reusable integration with existing factor and backtest systems,
3. deterministic and reviewable outputs,
4. tests around ranking and orchestration behavior.

Once this is stable, a later phase can add UI, parameter search, and more advanced research methods.
