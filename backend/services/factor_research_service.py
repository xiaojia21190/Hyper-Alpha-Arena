from __future__ import annotations

import json
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)
MIN_CANDIDATE_COVERAGE_RATIO = 0.6
MIN_THRESHOLD_SPREAD_SCORE = 0.05
FAST_BACKTEST_MIN_DAYS = 30
FAST_BACKTEST_MAX_DAYS = 60
FAST_BACKTEST_SYMBOL_LIMIT = 10
FULL_BACKTEST_LIMIT = 3

DEFAULT_RESEARCH_RUN_CONFIG = {
    "exchange": "hyperliquid",
    "top_n_symbols": 20,
    "lookback_days": 180,
    "objective": "return_over_drawdown",
    "factor_scope": "builtin_only",
    "period": "1h",
    "prescreen_limit": 10,
    "auto_promote_paper": False,
    "paper_account_id": 0,
    "auto_promote_live": False,
    "live_account_id": 0,
    "live_min_observation_hours": 24.0,
    "live_min_trades": 10,
    "live_min_net_pnl": 0.0,
    "live_min_win_rate": 50.0,
    "live_max_drawdown_percent": 20.0,
    "require_live_confirm": True,
}


def get_all_ticker_data_from_hyperliquid(environment: str = "mainnet") -> list[dict]:
    try:
        from services.hyperliquid_market_data import (
            get_all_ticker_data_from_hyperliquid as load_all_ticker_data,
        )
        return load_all_ticker_data(environment=environment)
    except Exception as exc:
        logger.warning(
            "[FactorResearch] get_all_ticker_data_from_hyperliquid import fallback: %s",
            exc,
        )
        try:
            from services.hyperliquid_market_data import HyperliquidClient

            return HyperliquidClient(environment=environment).get_all_ticker_data()
        except Exception:
            logger.exception(
                "[FactorResearch] Failed to load ticker rows for environment=%s",
                environment,
            )
            return []


def calculate_return_over_drawdown_score(
    total_pnl_percent: float,
    max_drawdown_percent: float,
    floor_value: float = 1.0,
) -> float:
    return total_pnl_percent / max(max_drawdown_percent, floor_value)


def collect_builtin_factor_names(
    registry_names: list[str],
    builtin_expression_names: list[str],
) -> list[str]:
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


def sort_symbols_by_volume(rows: list[dict], limit: int) -> list[str]:
    if limit <= 0:
        return []

    sortable_rows: list[tuple[float, str]] = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        volume = row.get("volume24h")
        if not symbol or volume is None:
            continue

        try:
            sortable_rows.append((float(volume), symbol))
        except (TypeError, ValueError):
            continue

    ranked_symbols: list[str] = []
    seen_symbols: set[str] = set()
    for _, symbol in sorted(sortable_rows, reverse=True):
        if symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        ranked_symbols.append(symbol)
        if len(ranked_symbols) >= limit:
            break
    return ranked_symbols


def resolve_top_hyperliquid_symbols(
    limit: int = 20,
    environment: str = "mainnet",
) -> list[str]:
    rows = get_all_ticker_data_from_hyperliquid(environment=environment)
    return sort_symbols_by_volume(rows, limit)


def map_factor_direction(ic_value: float | None) -> dict[str, str]:
    if ic_value is not None and ic_value < 0:
        return {"high_signal": "short", "low_signal": "long"}
    return {"high_signal": "long", "low_signal": "short"}


def _interpolate_percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot compute percentile for an empty series")

    if len(sorted_values) == 1:
        return float(sorted_values[0])

    position = (len(sorted_values) - 1) * percentile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    lower_value = float(sorted_values[lower_index])
    upper_value = float(sorted_values[upper_index])
    if lower_index == upper_index:
        return lower_value

    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight


def build_percentile_thresholds(values: list[float]) -> dict[str, float]:
    numeric_values = sorted(float(value) for value in values)
    return {
        "p20": round(_interpolate_percentile(numeric_values, 0.2), 6),
        "p50": round(_interpolate_percentile(numeric_values, 0.5), 6),
        "p80": round(_interpolate_percentile(numeric_values, 0.8), 6),
    }


def build_symbol_thresholds(
    series_by_symbol: dict[str, list[float]],
) -> dict[str, dict[str, float]]:
    thresholds_by_symbol: dict[str, dict[str, float]] = {}
    for symbol, values in series_by_symbol.items():
        if not values:
            continue
        thresholds_by_symbol[str(symbol)] = build_percentile_thresholds(values)
    return thresholds_by_symbol


def calculate_threshold_spread_score(thresholds: dict[str, float]) -> float:
    p20 = float(thresholds["p20"])
    p50 = float(thresholds["p50"])
    p80 = float(thresholds["p80"])

    total_span = abs(p80 - p20)
    if total_span <= 0:
        return 0.0

    scale = max(abs(p20), abs(p50), abs(p80), 1.0)
    spread_ratio = min(total_span / scale, 1.0)
    lower_span = abs(p50 - p20)
    upper_span = abs(p80 - p50)
    balance_ratio = 1.0 - min(abs(upper_span - lower_span) / total_span, 1.0)
    return round(spread_ratio * (0.5 + 0.5 * balance_ratio), 6)


def calculate_candidate_prescreen_score(
    avg_icir: float | None,
    avg_ic_mean: float | None,
    coverage_ratio: float,
    threshold_spread_score: float,
) -> float:
    icir_strength = min(abs(avg_icir or 0.0) / 2.0, 1.0)
    ic_mean_strength = min(abs(avg_ic_mean or 0.0) / 0.08, 1.0)
    score = (
        icir_strength * 0.35
        + ic_mean_strength * 0.25
        + min(max(coverage_ratio, 0.0), 1.0) * 0.30
        + min(max(threshold_spread_score, 0.0), 1.0) * 0.10
    )
    return round(score, 6)


def build_staged_backtest_plan(
    lookback_days: int,
    symbol_count: int,
    candidate_count: int,
) -> dict[str, int | bool]:
    fast_backtest_days = min(
        lookback_days,
        min(
            FAST_BACKTEST_MAX_DAYS,
            max(FAST_BACKTEST_MIN_DAYS, max(lookback_days // 4, 1)),
        ),
    )
    return {
        "use_fast_stage": candidate_count > FULL_BACKTEST_LIMIT and fast_backtest_days < lookback_days,
        "fast_backtest_days": fast_backtest_days,
        "fast_symbol_count": min(symbol_count, FAST_BACKTEST_SYMBOL_LIMIT),
        "full_backtest_limit": min(candidate_count, FULL_BACKTEST_LIMIT),
    }


def generate_factor_strategy_code(
    factor_name: str,
    period: str,
    thresholds: dict[str, float],
    direction: dict[str, str],
    symbols: list[str],
    thresholds_by_symbol: Optional[dict[str, dict[str, float]]] = None,
) -> str:
    symbols_literal = "[" + ", ".join(f'"{symbol}"' for symbol in symbols) + "]"
    p20 = thresholds["p20"]
    p50 = thresholds["p50"]
    p80 = thresholds["p80"]
    high_signal = direction["high_signal"]
    low_signal = direction["low_signal"]
    default_thresholds_literal = json.dumps(
        {"p20": p20, "p50": p50, "p80": p80},
        sort_keys=True,
    )
    symbol_thresholds_literal = json.dumps(
        thresholds_by_symbol or {},
        sort_keys=True,
    )

    return f"""
class FactorResearchStrategy:
    def should_trade(self, data):
        symbols = {symbols_literal}
        high_signal = "{high_signal}"
        low_signal = "{low_signal}"
        default_thresholds = {default_thresholds_literal}
        thresholds_by_symbol = {symbol_thresholds_literal}

        for symbol in symbols:
            position = data.positions.get(symbol)
            factor = data.get_factor(symbol, "{factor_name}", period="{period}")
            value = factor.get("value") if factor else None
            if value is None:
                continue
            symbol_threshold = thresholds_by_symbol.get(symbol, default_thresholds)
            symbol_p50 = symbol_threshold["p50"]

            price = data.get_price(symbol)
            if price <= 0:
                continue

            if position:
                if position.side == "long" and value <= symbol_p50:
                    return Decision(
                        operation="close",
                        symbol=symbol,
                        target_portion_of_balance=1.0,
                        leverage=1,
                        min_price=price * 0.999,
                        reason=f"Close long on {factor_name} mean reversion"
                    )

                if position.side == "short" and value >= symbol_p50:
                    return Decision(
                        operation="close",
                        symbol=symbol,
                        target_portion_of_balance=1.0,
                        leverage=1,
                        max_price=price * 1.001,
                        reason=f"Close short on {factor_name} mean reversion"
                    )

        strongest_signal = None

        for symbol in symbols:
            if data.positions.get(symbol):
                continue

            factor = data.get_factor(symbol, "{factor_name}", period="{period}")
            value = factor.get("value") if factor else None
            if value is None:
                continue
            symbol_threshold = thresholds_by_symbol.get(symbol, default_thresholds)
            symbol_p20 = symbol_threshold["p20"]
            symbol_p80 = symbol_threshold["p80"]
            symbol_span = max(abs(symbol_p80 - symbol_p20), 1e-09)

            if value >= symbol_p80:
                signal = high_signal
                score = abs(value - symbol_p80) / symbol_span
            elif value <= symbol_p20:
                signal = low_signal
                score = abs(symbol_p20 - value) / symbol_span
            else:
                continue

            if strongest_signal is None or score > strongest_signal["score"]:
                strongest_signal = {{
                    "symbol": symbol,
                    "signal": signal,
                    "value": value,
                    "score": score,
                }}

        if strongest_signal is None:
            fallback_symbol = data.trigger_symbol or (symbols[0] if symbols else "")
            return Decision(operation="hold", symbol=fallback_symbol, reason="No factor trigger")

        symbol = strongest_signal["symbol"]
        price = data.get_price(symbol)
        if price <= 0:
            return Decision(operation="hold", symbol=symbol, reason="Price unavailable")

        if strongest_signal["signal"] == "long":
            return Decision(
                operation="buy",
                symbol=symbol,
                target_portion_of_balance=0.2,
                leverage=2,
                max_price=price * 1.001,
                reason=f"{factor_name} high-signal long trigger"
            )

        return Decision(
            operation="sell",
            symbol=symbol,
            target_portion_of_balance=0.2,
            leverage=2,
            min_price=price * 0.999,
            reason=f"{factor_name} low-signal short trigger"
        )
""".strip()


def build_research_backtest_config(
    code: str,
    symbols: list[str],
    start_time_ms: int,
    end_time_ms: int,
    exchange: str = "hyperliquid",
):
    from backtest.models import BacktestConfig

    return BacktestConfig(
        code=code,
        signal_pool_ids=[],
        symbols=symbols,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        scheduled_interval_sec=3600,
        exchange=exchange,
        preload_periods=["1h"],
        intrabar_tp_sl_period=None,
    )


class FactorResearchService:
    def __init__(
        self,
        db: Any,
        backtest_engine_factory: Optional[Callable[[Any], Any]] = None,
        factor_effectiveness_service: Any = None,
        now_ms_factory: Optional[Callable[[], int]] = None,
    ):
        self.db = db
        self.backtest_engine_factory = backtest_engine_factory
        self.factor_effectiveness_service = factor_effectiveness_service
        self.now_ms_factory = now_ms_factory or (lambda: int(time.time() * 1000))
        self._progress_callback: Optional[Callable[[dict[str, Any]], None]] = None
        self._latest_factor_series_by_symbol_bundle: dict[str, dict[str, list[float]]] = {}

    def set_progress_callback(
        self,
        callback: Optional[Callable[[dict[str, Any]], None]],
    ) -> None:
        self._progress_callback = callback

    def resolve_universe(self, exchange: str, limit: int) -> list[str]:
        if exchange != "hyperliquid":
            raise ValueError(f"Unsupported research exchange: {exchange}")
        return resolve_top_hyperliquid_symbols(limit=limit)

    def collect_factor_names(self, factor_scope: str) -> list[str]:
        if factor_scope != "builtin_only":
            raise ValueError(f"Unsupported factor scope: {factor_scope}")

        from services.factor_registry import FACTOR_REGISTRY

        registry_names = [row["name"] for row in FACTOR_REGISTRY]
        builtin_expression_names = self._get_builtin_expression_names()
        return collect_builtin_factor_names(registry_names, builtin_expression_names)

    def ensure_effectiveness(self, exchange: str, symbols: list[str], period: str) -> dict:
        service = self._get_effectiveness_service()
        set_progress_callback = getattr(service, "set_progress_callback", None)
        if callable(set_progress_callback):
            set_progress_callback(
                lambda progress: self._emit_progress(
                    phase="ensure_effectiveness",
                    current=int(progress.get("symbol_completed", 0) or 0),
                    total=int(progress.get("symbol_total", len(symbols)) or len(symbols)),
                    current_factor=progress.get("current_factor") or None,
                    current_symbol=progress.get("current_symbol") or None,
                    factor_completed=progress.get("factor_completed"),
                    factor_total=progress.get("factor_total"),
                    effectiveness_status=progress.get("status"),
                )
            )
        try:
            return service.compute_for_exchange(
                self.db,
                exchange,
                period=period,
                force=False,
                symbols_override=symbols,
            )
        finally:
            if callable(set_progress_callback):
                set_progress_callback(None)

    def build_factor_candidates(
        self,
        exchange: str,
        symbols: list[str],
        factor_names: list[str],
        lookback_days: int,
        period: str,
    ) -> list[dict]:
        effectiveness_summary = self._load_effectiveness_summary(
            exchange=exchange,
            symbols=symbols,
            factor_names=factor_names,
            period=period,
        )
        factor_series_bundle = self._load_factor_series_bundle(
            exchange=exchange,
            symbols=symbols,
            factor_names=factor_names,
            lookback_days=lookback_days,
            period=period,
        )
        factor_categories = self._load_factor_categories(factor_names)
        factor_series_by_symbol_bundle = dict(self._latest_factor_series_by_symbol_bundle or {})
        candidates: list[dict] = []
        min_symbols_with_effectiveness = max(
            1,
            math.ceil(len(symbols) * MIN_CANDIDATE_COVERAGE_RATIO),
        )

        for factor_name in factor_names:
            series_values = factor_series_bundle.get(factor_name, [])
            if not series_values:
                continue

            summary = effectiveness_summary.get(factor_name, {})
            thresholds = build_percentile_thresholds(series_values)
            thresholds_by_symbol = build_symbol_thresholds(
                factor_series_by_symbol_bundle.get(factor_name, {})
            )
            symbols_with_effectiveness = int(summary.get("symbols_with_effectiveness", 0) or 0)
            coverage_ratio = (
                symbols_with_effectiveness / len(symbols)
                if symbols
                else 0.0
            )
            threshold_spread_score = calculate_threshold_spread_score(thresholds)

            if symbols_with_effectiveness < min_symbols_with_effectiveness:
                continue
            if threshold_spread_score < MIN_THRESHOLD_SPREAD_SCORE:
                continue

            candidates.append(
                {
                    "factor_name": factor_name,
                    "category": factor_categories.get(factor_name, "uncategorized"),
                    "thresholds": thresholds,
                    "thresholds_by_symbol": thresholds_by_symbol,
                    "direction": map_factor_direction(summary.get("avg_ic_mean")),
                    "avg_ic_mean": summary.get("avg_ic_mean"),
                    "avg_icir": summary.get("avg_icir"),
                    "symbols_with_effectiveness": symbols_with_effectiveness,
                    "coverage_ratio": round(coverage_ratio, 6),
                    "threshold_spread_score": threshold_spread_score,
                    "prescreen_score": calculate_candidate_prescreen_score(
                        avg_icir=summary.get("avg_icir"),
                        avg_ic_mean=summary.get("avg_ic_mean"),
                        coverage_ratio=coverage_ratio,
                        threshold_spread_score=threshold_spread_score,
                    ),
                }
            )

        candidates.sort(
            key=lambda row: (
                row.get("prescreen_score", float("-inf")),
                abs(row.get("avg_icir") or 0.0),
                abs(row.get("avg_ic_mean") or 0.0),
                row["factor_name"],
            ),
            reverse=True,
        )
        return candidates

    def backtest_factor(
        self,
        candidate: dict,
        symbols: list[str],
        start_time_ms: int,
        end_time_ms: int,
        exchange: str,
        period: str,
    ) -> dict:
        code = generate_factor_strategy_code(
            factor_name=candidate["factor_name"],
            period=period,
            thresholds=candidate["thresholds"],
            thresholds_by_symbol=candidate.get("thresholds_by_symbol"),
            direction=candidate["direction"],
            symbols=symbols,
        )
        config = build_research_backtest_config(
            code=code,
            symbols=symbols,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            exchange=exchange,
        )
        result = self._create_backtest_engine().run(config)

        if not getattr(result, "success", False):
            return {
                **candidate,
                "score": float("-inf"),
                "total_pnl_percent": float("-inf"),
                "max_drawdown_percent": float("inf"),
                "sharpe_ratio": float("-inf"),
                "total_trades": 0,
                "symbols_tested": len(symbols),
                "success": False,
            }

        return {
            **candidate,
            "score": round(
                calculate_return_over_drawdown_score(
                    total_pnl_percent=result.total_pnl_percent,
                    max_drawdown_percent=result.max_drawdown_percent,
                ),
                6,
            ),
            "total_pnl_percent": round(result.total_pnl_percent, 6),
            "max_drawdown_percent": round(result.max_drawdown_percent, 6),
            "sharpe_ratio": round(result.sharpe_ratio, 6),
            "total_trades": result.total_trades,
            "symbols_tested": len(symbols),
            "success": True,
        }

    def run_research(
        self,
        exchange: str = "hyperliquid",
        top_n_symbols: int = 20,
        lookback_days: int = 180,
        objective: str = "return_over_drawdown",
        factor_scope: str = "builtin_only",
        period: str = "1h",
        prescreen_limit: int = 10,
        auto_promote_paper: bool = False,
        paper_account_id: int = 0,
        auto_promote_live: bool = False,
        live_account_id: int = 0,
        live_min_observation_hours: float = 24.0,
        live_min_trades: int = 10,
        live_min_net_pnl: float = 0.0,
        live_min_win_rate: float = 50.0,
        live_max_drawdown_percent: float = 20.0,
        require_live_confirm: bool = True,
    ) -> dict:
        if objective != "return_over_drawdown":
            raise ValueError(f"Unsupported research objective: {objective}")

        self._emit_progress(
            phase="preparing",
            current=0,
            total=0,
            current_factor=None,
        )
        symbols = self.resolve_universe(exchange, top_n_symbols)
        factor_names = self.collect_factor_names(factor_scope)
        self._emit_progress(
            phase="ensure_effectiveness",
            current=0,
            total=len(symbols),
            current_factor=None,
        )
        self.ensure_effectiveness(exchange, symbols, period)

        candidates = self.build_factor_candidates(
            exchange=exchange,
            symbols=symbols,
            factor_names=factor_names,
            lookback_days=lookback_days,
            period=period,
        )
        if prescreen_limit > 0:
            candidates = candidates[:prescreen_limit]

        staged_plan = build_staged_backtest_plan(
            lookback_days=lookback_days,
            symbol_count=len(symbols),
            candidate_count=len(candidates),
        )
        self._emit_progress(
            phase="candidate_prescreen",
            current=len(candidates),
            total=len(factor_names),
            current_factor=None,
            candidate_count=len(candidates),
            fast_candidate_count=(
                len(candidates) if staged_plan["use_fast_stage"] else 0
            ),
            full_backtest_candidate_count=(
                int(staged_plan["full_backtest_limit"])
                if staged_plan["use_fast_stage"]
                else len(candidates)
            ),
            fast_backtest_days=(
                int(staged_plan["fast_backtest_days"])
                if staged_plan["use_fast_stage"]
                else None
            ),
            fast_backtest_symbol_count=(
                int(staged_plan["fast_symbol_count"])
                if staged_plan["use_fast_stage"]
                else None
            ),
        )
        end_time_ms = self.now_ms_factory()
        start_time_ms = end_time_ms - lookback_days * 24 * 60 * 60 * 1000

        fast_ranked_results: list[dict] = []
        full_backtest_candidates = list(candidates)
        if staged_plan["use_fast_stage"] and candidates:
            fast_symbols = symbols[: int(staged_plan["fast_symbol_count"])]
            fast_lookback_days = int(staged_plan["fast_backtest_days"])
            fast_start_time_ms = end_time_ms - fast_lookback_days * 24 * 60 * 60 * 1000
            fast_results = self._backtest_candidates(
                phase="fast_backtest",
                candidates=candidates,
                symbols=fast_symbols,
                start_time_ms=fast_start_time_ms,
                end_time_ms=end_time_ms,
                exchange=exchange,
                period=period,
                candidate_count=len(candidates),
                fast_candidate_count=len(candidates),
                full_backtest_candidate_count=int(staged_plan["full_backtest_limit"]),
                fast_backtest_days=fast_lookback_days,
                fast_backtest_symbol_count=len(fast_symbols),
            )
            fast_ranked_results = rank_factor_results(
                [row for row in fast_results if row.get("success", True)]
            )
            selected_names = [
                row["factor_name"]
                for row in fast_ranked_results[: int(staged_plan["full_backtest_limit"])]
            ]
            candidate_by_name = {
                row["factor_name"]: row
                for row in candidates
            }
            full_backtest_candidates = [
                candidate_by_name[name]
                for name in selected_names
                if name in candidate_by_name
            ]
            if not full_backtest_candidates:
                full_backtest_candidates = candidates[
                    : int(staged_plan["full_backtest_limit"])
                ]

        results = self._backtest_candidates(
            phase="full_backtest",
            candidates=full_backtest_candidates,
            symbols=symbols,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            exchange=exchange,
            period=period,
            candidate_count=len(candidates),
            fast_candidate_count=(
                len(candidates) if staged_plan["use_fast_stage"] else 0
            ),
            full_backtest_candidate_count=len(full_backtest_candidates),
            fast_backtest_days=(
                int(staged_plan["fast_backtest_days"])
                if staged_plan["use_fast_stage"]
                else None
            ),
            fast_backtest_symbol_count=(
                int(staged_plan["fast_symbol_count"])
                if staged_plan["use_fast_stage"]
                else None
            ),
        )
        ranked_results = rank_factor_results(
            [row for row in results if row.get("success", True)]
        )
        top_factor = ranked_results[0] if ranked_results else None
        portfolio_candidates: list[dict] = []
        portfolio_ranked_results: list[dict] = []
        top_portfolio: Optional[dict] = None
        if ranked_results:
            from services.factor_portfolio_service import (
                build_portfolio_candidates,
                pick_recommended_portfolio,
                rank_portfolio_candidates,
            )

            portfolio_candidates = build_portfolio_candidates(
                ranked_results,
                top_n=min(5, len(ranked_results)),
                objective=objective,
            )
            portfolio_ranked_results = rank_portfolio_candidates(portfolio_candidates)
            top_portfolio = pick_recommended_portfolio(portfolio_ranked_results)

        run_id, persisted_portfolio_rows, persisted_top_portfolio = self._persist_research_run(
            run_config={
                "exchange": exchange,
                "top_n_symbols": top_n_symbols,
                "lookback_days": lookback_days,
                "objective": objective,
                "factor_scope": factor_scope,
                "period": period,
                "prescreen_limit": prescreen_limit,
            },
            result={
                "fast_ranked_results": fast_ranked_results[: int(staged_plan["full_backtest_limit"])],
                "ranked_results": ranked_results,
                "top_factor": top_factor,
                "portfolio_candidates": portfolio_candidates,
                "portfolio_ranked_results": portfolio_ranked_results,
                "top_portfolio": top_portfolio,
            },
        )
        if persisted_portfolio_rows:
            portfolio_candidates = persisted_portfolio_rows
            portfolio_ranked_results = persisted_portfolio_rows
        if persisted_top_portfolio is not None:
            top_portfolio = persisted_top_portfolio

        auto_paper_deployment: Optional[dict] = None
        if (
            auto_promote_paper
            and int(paper_account_id or 0) > 0
            and top_portfolio
            and top_portfolio.get("portfolio_id")
        ):
            try:
                from services.factor_portfolio_deployment_service import deploy_portfolio_candidate

                auto_paper_deployment = deploy_portfolio_candidate(
                    self.db,
                    portfolio_id=int(top_portfolio["portfolio_id"]),
                    account_id=int(paper_account_id),
                    mode="paper",
                    confirm_live=False,
                    period=period,
                    trigger_interval=3600,
                    signal_pool_ids=[],
                    require_live_confirm=require_live_confirm,
                    exchange=exchange,
                )
            except Exception:
                logger.exception("[FactorResearch] Auto paper deployment failed")

        auto_live_decision: Optional[dict] = None
        if (
            auto_promote_live
            and int(paper_account_id or 0) > 0
            and int(live_account_id or 0) > 0
            and top_portfolio
            and top_portfolio.get("portfolio_id")
        ):
            try:
                from services.factor_portfolio_deployment_service import (
                    auto_decide_live_promotion,
                )

                auto_live_decision = auto_decide_live_promotion(
                    self.db,
                    portfolio_id=int(top_portfolio["portfolio_id"]),
                    paper_account_id=int(paper_account_id),
                    live_account_id=int(live_account_id),
                    min_observation_hours=float(live_min_observation_hours),
                    min_trades=int(live_min_trades),
                    min_net_pnl=float(live_min_net_pnl),
                    min_win_rate=float(live_min_win_rate),
                    max_drawdown_percent_limit=float(live_max_drawdown_percent),
                    period=period,
                    trigger_interval=3600,
                    signal_pool_ids=[],
                    require_live_confirm=require_live_confirm,
                    exchange=exchange,
                    paper_deployment_id=(
                        (auto_paper_deployment or {}).get("deployment") or {}
                    ).get("id"),
                )
            except Exception:
                logger.exception("[FactorResearch] Auto live promotion decision failed")

        self._emit_progress(
            phase="complete",
            current=len(full_backtest_candidates),
            total=len(full_backtest_candidates),
            current_factor=top_factor.get("factor_name") if top_factor else None,
            candidate_count=len(candidates),
            fast_candidate_count=(
                len(candidates) if staged_plan["use_fast_stage"] else 0
            ),
            full_backtest_candidate_count=len(full_backtest_candidates),
            fast_backtest_days=(
                int(staged_plan["fast_backtest_days"])
                if staged_plan["use_fast_stage"]
                else None
            ),
            fast_backtest_symbol_count=(
                int(staged_plan["fast_symbol_count"])
                if staged_plan["use_fast_stage"]
                else None
            ),
        )

        return {
            "run_id": run_id,
            "exchange": exchange,
            "symbols": symbols,
            "top_n_symbols": top_n_symbols,
            "lookback_days": lookback_days,
            "objective": objective,
            "factor_scope": factor_scope,
            "candidate_count": len(candidates),
            "fast_candidate_count": len(candidates) if staged_plan["use_fast_stage"] else 0,
            "full_backtest_candidate_count": len(full_backtest_candidates),
            "fast_backtest_days": (
                int(staged_plan["fast_backtest_days"])
                if staged_plan["use_fast_stage"]
                else None
            ),
            "fast_backtest_symbol_count": (
                int(staged_plan["fast_symbol_count"])
                if staged_plan["use_fast_stage"]
                else None
            ),
            "fast_ranked_results": fast_ranked_results[
                : int(staged_plan["full_backtest_limit"])
            ],
            "ranked_results": ranked_results,
            "top_factor": top_factor,
            "portfolio_candidates": portfolio_candidates,
            "portfolio_ranked_results": portfolio_ranked_results,
            "top_portfolio": top_portfolio,
            "auto_paper_deployment": auto_paper_deployment,
            "auto_live_decision": auto_live_decision,
        }

    def _backtest_candidates(
        self,
        phase: str,
        candidates: list[dict],
        symbols: list[str],
        start_time_ms: int,
        end_time_ms: int,
        exchange: str,
        period: str,
        **progress_fields: Any,
    ) -> list[dict]:
        results: list[dict] = []
        total = len(candidates)
        for index, candidate in enumerate(candidates, start=1):
            self._emit_progress(
                phase=phase,
                current=index,
                total=total,
                current_factor=candidate["factor_name"],
                **progress_fields,
            )
            results.append(
                self.backtest_factor(
                    candidate=candidate,
                    symbols=symbols,
                    start_time_ms=start_time_ms,
                    end_time_ms=end_time_ms,
                    exchange=exchange,
                    period=period,
                )
            )
        return results

    def _emit_progress(self, phase: str, **fields: Any) -> None:
        if self._progress_callback is None:
            return
        payload = {
            "phase": phase,
            "updated_at": time.time(),
            **fields,
        }
        self._progress_callback(payload)

    def _create_backtest_engine(self):
        if self.backtest_engine_factory is not None:
            return self.backtest_engine_factory(self.db)

        from backtest.engine import ProgramBacktestEngine

        return ProgramBacktestEngine(self.db)

    def _get_effectiveness_service(self):
        if self.factor_effectiveness_service is not None:
            return self.factor_effectiveness_service

        from services.factor_effectiveness_service import FactorEffectivenessService

        self.factor_effectiveness_service = FactorEffectivenessService()
        return self.factor_effectiveness_service

    def _get_builtin_expression_names(self) -> list[str]:
        from database.models import CustomFactor

        rows = (
            self.db.query(CustomFactor.name)
            .filter(
                CustomFactor.is_active.is_(True),
                CustomFactor.source == "builtin_expression",
            )
            .all()
        )
        return [row[0] for row in rows]

    def _load_effectiveness_summary(
        self,
        exchange: str,
        symbols: list[str],
        factor_names: list[str],
        period: str,
    ) -> dict[str, dict]:
        if not symbols or not factor_names:
            return {}

        from database.models import FactorEffectiveness

        ordered_rows = (
            self.db.query(FactorEffectiveness)
            .filter(
                FactorEffectiveness.exchange == exchange,
                FactorEffectiveness.period == period,
                FactorEffectiveness.forward_period == "4h",
                FactorEffectiveness.symbol.in_(symbols),
                FactorEffectiveness.factor_name.in_(factor_names),
            )
            .order_by(
                FactorEffectiveness.factor_name,
                FactorEffectiveness.symbol,
                FactorEffectiveness.calc_date.desc(),
                FactorEffectiveness.created_at.desc(),
            )
            .all()
        )

        latest_rows = []
        seen_pairs: set[tuple[str, str]] = set()
        for row in ordered_rows:
            pair = (row.factor_name, row.symbol)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            latest_rows.append(row)

        summary: dict[str, dict[str, float]] = {}
        for row in latest_rows:
            factor_name = row.factor_name
            bucket = summary.setdefault(
                factor_name,
                {"ic_means": [], "icirs": [], "symbols_with_effectiveness": 0},
            )
            if row.ic_mean is not None:
                bucket["ic_means"].append(float(row.ic_mean))
            if row.icir is not None:
                bucket["icirs"].append(float(row.icir))
            bucket["symbols_with_effectiveness"] += 1

        result: dict[str, dict] = {}
        for factor_name, bucket in summary.items():
            ic_means = bucket["ic_means"]
            icirs = bucket["icirs"]
            result[factor_name] = {
                "avg_ic_mean": round(sum(ic_means) / len(ic_means), 6) if ic_means else None,
                "avg_icir": round(sum(icirs) / len(icirs), 6) if icirs else None,
                "symbols_with_effectiveness": bucket["symbols_with_effectiveness"],
            }
        return result

    def _load_factor_series_values(
        self,
        exchange: str,
        symbols: list[str],
        factor_name: str,
        lookback_days: int,
        period: str,
    ) -> list[float]:
        return self._load_factor_series_bundle(
            exchange=exchange,
            symbols=symbols,
            factor_names=[factor_name],
            lookback_days=lookback_days,
            period=period,
        ).get(factor_name, [])

    def _load_factor_series_bundle(
        self,
        exchange: str,
        symbols: list[str],
        factor_names: list[str],
        lookback_days: int,
        period: str,
    ) -> dict[str, list[float]]:
        from services.factor_data_provider import ensure_kline_coverage
        from services.factor_expression_engine import factor_expression_engine
        from services.factor_registry import FACTOR_REGISTRY
        from services.technical_indicators import calculate_indicators

        if not factor_names or not symbols:
            self._latest_factor_series_by_symbol_bundle = {}
            return {}

        extractor = self._get_effectiveness_service()
        bars = max(lookback_days * 24, 120)
        builtin_factors = {
            row["name"]: row
            for row in FACTOR_REGISTRY
            if row["name"] in factor_names
        }
        expression_factors = self._get_builtin_expression_rows(factor_names)
        tech_keys = sorted(
            {
                row.get("indicator_key")
                for row in builtin_factors.values()
                if row.get("compute_type") == "technical" and row.get("indicator_key")
            }
        )
        series_bundle = {factor_name: [] for factor_name in factor_names}
        series_by_symbol_bundle = {
            factor_name: {}
            for factor_name in factor_names
        }
        for symbol in symbols:
            klines = ensure_kline_coverage(
                self.db,
                exchange,
                symbol,
                period,
                min_bars=bars,
            )
            if not klines:
                continue

            sliced_klines = klines[-bars:]
            indicators = calculate_indicators(sliced_klines, tech_keys) if tech_keys else {}
            n_bars = len(sliced_klines)

            for factor_name, factor_def in builtin_factors.items():
                series = extractor._extract_full_series(
                    factor_def,
                    indicators,
                    sliced_klines,
                    n_bars,
                    self.db,
                    symbol,
                    exchange,
                )
                if series is None:
                    continue
                normalized_series = self._normalize_numeric_values(series)
                if not normalized_series:
                    continue
                series_bundle[factor_name].extend(normalized_series)
                series_by_symbol_bundle[factor_name][symbol] = normalized_series

            for factor_name, factor in expression_factors.items():
                series, _ = factor_expression_engine.execute(
                    factor.expression,
                    sliced_klines,
                )
                if series is None:
                    continue
                normalized_series = self._normalize_numeric_values(series.tolist())
                if not normalized_series:
                    continue
                series_bundle[factor_name].extend(normalized_series)
                series_by_symbol_bundle[factor_name][symbol] = normalized_series

        filtered_bundle = {
            factor_name: values
            for factor_name, values in series_bundle.items()
            if values
        }
        self._latest_factor_series_by_symbol_bundle = {
            factor_name: series_by_symbol_bundle.get(factor_name, {})
            for factor_name in filtered_bundle
        }
        return filtered_bundle

    def _get_builtin_expression_rows(
        self,
        factor_names: list[str],
    ) -> dict[str, Any]:
        from database.models import CustomFactor

        rows = (
            self.db.query(CustomFactor)
            .filter(
                CustomFactor.name.in_(factor_names),
                CustomFactor.is_active.is_(True),
                CustomFactor.source == "builtin_expression",
            )
            .all()
        )
        return {
            row.name: row
            for row in rows
        }

    def _load_factor_categories(self, factor_names: list[str]) -> dict[str, str]:
        if not factor_names:
            return {}

        categories: dict[str, str] = {}

        from services.factor_registry import FACTOR_REGISTRY

        for row in FACTOR_REGISTRY:
            name = row.get("name")
            if name in factor_names:
                categories[name] = row.get("category", "builtin")

        if not hasattr(self.db, "query"):
            return categories

        from database.models import CustomFactor

        expression_rows = (
            self.db.query(CustomFactor.name, CustomFactor.category)
            .filter(
                CustomFactor.name.in_(factor_names),
                CustomFactor.is_active.is_(True),
            )
            .all()
        )
        for name, category in expression_rows:
            categories[name] = category or "custom"

        return categories

    def _persist_research_run(
        self,
        run_config: dict[str, Any],
        result: dict[str, Any],
    ) -> tuple[Optional[int], list[dict[str, Any]], Optional[dict[str, Any]]]:
        required_attrs = ("add", "commit", "query")
        if not all(hasattr(self.db, attr) for attr in required_attrs):
            return None, [], result.get("top_portfolio")

        try:
            from database.models import FactorPortfolioCandidate, FactorResearchRun
        except Exception:
            return None, [], result.get("top_portfolio")

        started_at = datetime.now(timezone.utc)
        run_row = FactorResearchRun(
            exchange=run_config.get("exchange", "hyperliquid"),
            top_n_symbols=int(run_config.get("top_n_symbols", 20)),
            lookback_days=int(run_config.get("lookback_days", 180)),
            objective=run_config.get("objective", "return_over_drawdown"),
            factor_scope=run_config.get("factor_scope", "builtin_only"),
            period=run_config.get("period", "1h"),
            prescreen_limit=int(run_config.get("prescreen_limit", 10)),
            status="success",
            result_json=json.dumps(result, ensure_ascii=False),
            top_factor_json=json.dumps(result.get("top_factor"), ensure_ascii=False),
            top_portfolio_json=json.dumps(result.get("top_portfolio"), ensure_ascii=False),
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

        try:
            self.db.add(run_row)
            self.db.commit()
            if hasattr(self.db, "refresh"):
                self.db.refresh(run_row)
        except Exception:
            logger.exception("[FactorResearch] Failed to persist factor research run")
            return None, [], result.get("top_portfolio")

        top_portfolio = result.get("top_portfolio") or {}
        recommended_name = top_portfolio.get("name")
        persisted_portfolio_rows: list[dict[str, Any]] = []
        persisted_top_portfolio: Optional[dict[str, Any]] = None
        for candidate in result.get("portfolio_ranked_results") or []:
            weights = candidate.get("weights", [])
            row = FactorPortfolioCandidate(
                run_id=run_row.id,
                name=candidate.get("name", candidate.get("construction_method", "portfolio")),
                construction_method=candidate.get("construction_method", "unknown"),
                score=float(candidate.get("score", 0.0) or 0.0),
                component_count=len(weights),
                components_json=json.dumps(weights, ensure_ascii=False),
                metrics_json=json.dumps(
                    {
                        "weighted_total_pnl_percent": candidate.get("weighted_total_pnl_percent"),
                        "weighted_max_drawdown_percent": candidate.get("weighted_max_drawdown_percent"),
                        "weighted_sharpe_ratio": candidate.get("weighted_sharpe_ratio"),
                        "rationale": candidate.get("rationale"),
                    },
                    ensure_ascii=False,
                ),
                is_recommended=candidate.get("name") == recommended_name,
            )
            self.db.add(row)
            try:
                self.db.commit()
                if hasattr(self.db, "refresh"):
                    self.db.refresh(row)
            except Exception:
                logger.exception("[FactorResearch] Failed to persist portfolio candidate")
                continue
            persisted_candidate = {
                **candidate,
                "portfolio_id": row.id,
                "run_id": run_row.id,
            }
            persisted_portfolio_rows.append(persisted_candidate)
            if row.is_recommended:
                persisted_top_portfolio = persisted_candidate

        if persisted_top_portfolio is None and persisted_portfolio_rows:
            persisted_top_portfolio = persisted_portfolio_rows[0]
        if persisted_top_portfolio is None and result.get("top_portfolio"):
            persisted_top_portfolio = result.get("top_portfolio")
        if persisted_top_portfolio is not None:
            try:
                run_row.top_portfolio_json = json.dumps(persisted_top_portfolio, ensure_ascii=False)
                self.db.commit()
            except Exception:
                logger.exception("[FactorResearch] Failed to update persisted top portfolio snapshot")
        return run_row.id, persisted_portfolio_rows, persisted_top_portfolio

    def _normalize_numeric_values(self, series: Any) -> list[float]:
        if not series:
            return []

        numeric_values: list[float] = []
        for value in series:
            if value is None:
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(numeric_value):
                continue
            numeric_values.append(numeric_value)
        return numeric_values


class FactorResearchAutomationService:
    TASK_ID = "factor_research_automation"

    def __init__(
        self,
        scheduler: Any = None,
        session_factory: Optional[Callable[[], Any]] = None,
        research_service_factory: Optional[Callable[[Any], FactorResearchService]] = None,
    ):
        if scheduler is None:
            from services.scheduler import task_scheduler

            scheduler = task_scheduler
        if session_factory is None:
            from database.connection import SessionLocal

            session_factory = SessionLocal

        self.scheduler = scheduler
        self.session_factory = session_factory
        self.research_service_factory = research_service_factory or FactorResearchService
        self._running = False
        self._status = "idle"
        self._interval_seconds: Optional[int] = None
        self._config = dict(DEFAULT_RESEARCH_RUN_CONFIG)
        self._last_error: Optional[str] = None
        self._last_result: Optional[dict] = None
        self._last_top_factor: Optional[dict] = None
        self._last_top_portfolio: Optional[dict] = None
        self._last_run_status: Optional[str] = None
        self._last_run_started_at: Optional[float] = None
        self._last_run_completed_at: Optional[float] = None
        self._progress: Optional[dict[str, Any]] = None
        self._lock = threading.Lock()
        self._current_thread: Optional[threading.Thread] = None
        self._hydrate_last_persisted_status()

    def start(self, interval_seconds: int, run_immediately: bool = False, **config: Any) -> None:
        self._interval_seconds = int(interval_seconds)
        self._config = self._merge_config(config)
        self.scheduler.remove_task(self.TASK_ID)
        self.scheduler.add_interval_task(
            task_func=self._run,
            interval_seconds=self._interval_seconds,
            task_id=self.TASK_ID,
        )
        self._running = True
        logger.info(
            "[FactorResearch] Scheduled automation every %ss for %s top %s lookback %sd",
            self._interval_seconds,
            self._config["exchange"],
            self._config["top_n_symbols"],
            self._config["lookback_days"],
        )
        if run_immediately:
            self.trigger_run()

    def stop(self) -> None:
        self.scheduler.remove_task(self.TASK_ID)
        self._running = False
        if self._status == "running" and not self._has_active_run():
            self._status = "idle"

    def run_now(self, **overrides: Any) -> dict:
        config = self._merge_config(overrides)
        self._validate_config(config)
        with self._lock:
            if self._has_active_run_locked():
                raise RuntimeError("Factor research run is already in progress")
            self._config = dict(config)
            self._mark_run_started_locked()
        return self._execute_run(config, mark_started=False)

    def trigger_run(self, **overrides: Any) -> dict:
        config = self._merge_config(overrides)
        self._validate_config(config)
        with self._lock:
            if self._has_active_run_locked():
                return {
                    "status": "already_running",
                    "config": config,
                }
            self._config = dict(config)
            self._mark_run_started_locked()
            worker = threading.Thread(
                target=self._execute_run_background,
                args=(config,),
                daemon=True,
                name="factor-research-runner",
            )
            self._current_thread = worker
            worker.start()
        return {
            "status": "started",
            "config": config,
        }

    def get_status(self) -> dict:
        return {
            "enabled": self._running,
            "status": self._status,
            "interval_seconds": self._interval_seconds,
            "config": dict(self._config),
            "last_run_status": self._last_run_status,
            "last_run_started_at": self._last_run_started_at,
            "last_run_completed_at": self._last_run_completed_at,
            "last_error": self._last_error,
            "last_top_factor": self._last_top_factor,
            "last_top_portfolio": self._last_top_portfolio,
            "last_result": self._last_result,
            "progress": dict(self._progress) if self._progress is not None else None,
        }

    def _run(self) -> None:
        self.trigger_run()

    def _execute_run(self, config: dict[str, Any], mark_started: bool = True) -> dict:
        db = self.session_factory()
        if mark_started:
            with self._lock:
                if self._has_active_run_locked():
                    raise RuntimeError("Factor research run is already in progress")
                self._config = dict(config)
                self._mark_run_started_locked()

        try:
            research_service = self.research_service_factory(db)
            set_progress_callback = getattr(research_service, "set_progress_callback", None)
            if callable(set_progress_callback):
                set_progress_callback(self._update_progress)
            result = research_service.run_research(**config)
            with self._lock:
                self._last_result = result
                self._last_top_factor = result.get("top_factor")
                self._last_top_portfolio = result.get("top_portfolio")
                self._last_run_status = "success"
                progress = dict(self._progress or {})
                progress.update(
                    {
                        "phase": "complete",
                        "current": result.get(
                            "full_backtest_candidate_count",
                            result.get("candidate_count", 0),
                        ),
                        "total": result.get(
                            "full_backtest_candidate_count",
                            result.get("candidate_count", 0),
                        ),
                        "current_factor": (
                            (result.get("top_factor") or {}).get("factor_name")
                        ),
                        "candidate_count": result.get("candidate_count", 0),
                        "fast_candidate_count": result.get("fast_candidate_count", 0),
                        "full_backtest_candidate_count": result.get(
                            "full_backtest_candidate_count",
                            result.get("candidate_count", 0),
                        ),
                        "fast_backtest_days": result.get("fast_backtest_days"),
                        "fast_backtest_symbol_count": result.get(
                            "fast_backtest_symbol_count"
                        ),
                        "updated_at": time.time(),
                    }
                )
                self._progress = progress
            return result
        except Exception as exc:
            with self._lock:
                self._last_error = str(exc)
                self._last_run_status = "error"
                progress = dict(self._progress or {})
                progress.update(
                    {
                        "phase": "error",
                        "error": str(exc),
                        "updated_at": time.time(),
                    }
                )
                self._progress = progress
            logger.exception("[FactorResearch] Automated run failed")
            raise
        finally:
            with self._lock:
                self._last_run_completed_at = time.time()
                self._status = "idle"
                self._current_thread = None
            close = getattr(db, "close", None)
            if callable(close):
                close()

    def _execute_run_background(self, config: dict[str, Any]) -> None:
        self._execute_run(config, mark_started=False)

    def _merge_config(self, overrides: dict[str, Any]) -> dict[str, Any]:
        config = dict(DEFAULT_RESEARCH_RUN_CONFIG)
        config.update(self._config)
        for key, value in overrides.items():
            if value is not None:
                config[key] = value
        return config

    def _validate_config(self, config: dict[str, Any]) -> None:
        if config.get("exchange") != "hyperliquid":
            raise ValueError(f"Unsupported research exchange: {config.get('exchange')}")
        if config.get("objective") != "return_over_drawdown":
            raise ValueError(
                f"Unsupported research objective: {config.get('objective')}"
            )
        if config.get("factor_scope") != "builtin_only":
            raise ValueError(
                f"Unsupported factor scope: {config.get('factor_scope')}"
            )

    def _has_active_run(self) -> bool:
        with self._lock:
            return self._has_active_run_locked()

    def _has_active_run_locked(self) -> bool:
        return self._status == "running" or (
            self._current_thread is not None and self._current_thread.is_alive()
        )

    def _mark_run_started_locked(self) -> None:
        self._status = "running"
        self._last_run_status = "running"
        self._last_error = None
        self._last_run_started_at = time.time()
        self._progress = {
            "phase": "queued",
            "current": 0,
            "total": 0,
            "current_factor": None,
            "updated_at": self._last_run_started_at,
        }

    def _update_progress(self, progress: dict[str, Any]) -> None:
        with self._lock:
            merged_progress = dict(self._progress or {})
            merged_progress.update(progress)
            merged_progress["updated_at"] = progress.get("updated_at", time.time())
            self._progress = merged_progress

    @staticmethod
    def _parse_json_safe(payload: Any) -> Optional[dict[str, Any]]:
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload
        if not isinstance(payload, str) or payload.strip() == "":
            return None
        try:
            loaded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None

    @staticmethod
    def _to_unix_timestamp(value: Optional[datetime]) -> Optional[float]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    def _hydrate_last_persisted_status(self) -> None:
        db = None
        try:
            db = self.session_factory()
            if not hasattr(db, "query"):
                return
            from database.models import FactorResearchRun

            run = (
                db.query(FactorResearchRun)
                .filter(FactorResearchRun.status == "success")
                .order_by(FactorResearchRun.created_at.desc(), FactorResearchRun.id.desc())
                .first()
            )
            if run is None:
                return

            parsed_result = self._parse_json_safe(getattr(run, "result_json", None))
            parsed_top_factor = self._parse_json_safe(getattr(run, "top_factor_json", None))
            parsed_top_portfolio = self._parse_json_safe(
                getattr(run, "top_portfolio_json", None)
            )

            self._config = {
                **dict(DEFAULT_RESEARCH_RUN_CONFIG),
                "exchange": getattr(run, "exchange", DEFAULT_RESEARCH_RUN_CONFIG["exchange"]),
                "top_n_symbols": int(
                    getattr(run, "top_n_symbols", DEFAULT_RESEARCH_RUN_CONFIG["top_n_symbols"])
                ),
                "lookback_days": int(
                    getattr(run, "lookback_days", DEFAULT_RESEARCH_RUN_CONFIG["lookback_days"])
                ),
                "objective": getattr(run, "objective", DEFAULT_RESEARCH_RUN_CONFIG["objective"]),
                "factor_scope": getattr(
                    run, "factor_scope", DEFAULT_RESEARCH_RUN_CONFIG["factor_scope"]
                ),
                "period": getattr(run, "period", DEFAULT_RESEARCH_RUN_CONFIG["period"]),
                "prescreen_limit": int(
                    getattr(
                        run,
                        "prescreen_limit",
                        DEFAULT_RESEARCH_RUN_CONFIG["prescreen_limit"],
                    )
                ),
            }
            self._last_result = parsed_result
            self._last_top_factor = parsed_top_factor or (
                (parsed_result or {}).get("top_factor") if parsed_result else None
            )
            self._last_top_portfolio = parsed_top_portfolio or (
                (parsed_result or {}).get("top_portfolio") if parsed_result else None
            )
            self._last_error = None
            self._last_run_status = "success"
            self._last_run_started_at = self._to_unix_timestamp(
                getattr(run, "started_at", None)
            )
            self._last_run_completed_at = self._to_unix_timestamp(
                getattr(run, "completed_at", None)
            )

            candidate_count = 0
            top_factor_name = None
            if isinstance(parsed_result, dict):
                candidate_count = int(
                    parsed_result.get(
                        "full_backtest_candidate_count",
                        parsed_result.get("candidate_count", 0),
                    )
                    or 0
                )
                top_factor_name = ((parsed_result.get("top_factor") or {}).get("factor_name"))
            self._progress = {
                "phase": "complete",
                "current": candidate_count,
                "total": candidate_count,
                "current_factor": top_factor_name,
                "candidate_count": int(
                    ((parsed_result or {}).get("candidate_count", 0)) if parsed_result else 0
                ),
                "fast_candidate_count": int(
                    ((parsed_result or {}).get("fast_candidate_count", 0))
                    if parsed_result
                    else 0
                ),
                "full_backtest_candidate_count": candidate_count,
                "fast_backtest_days": (parsed_result or {}).get("fast_backtest_days")
                if parsed_result
                else None,
                "fast_backtest_symbol_count": (
                    (parsed_result or {}).get("fast_backtest_symbol_count")
                    if parsed_result
                    else None
                ),
                "updated_at": time.time(),
            }
        except Exception:
            logger.exception("[FactorResearch] Failed to hydrate last persisted run status")
        finally:
            close = getattr(db, "close", None)
            if callable(close):
                close()


factor_research_automation_service = FactorResearchAutomationService()
