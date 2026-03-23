import time
from datetime import datetime, timezone

from services import factor_research_service as factor_research_service_module
from services.factor_research_service import (
    calculate_candidate_prescreen_score,
    build_percentile_thresholds,
    build_staged_backtest_plan,
    build_research_backtest_config,
    calculate_return_over_drawdown_score,
    calculate_threshold_spread_score,
    collect_builtin_factor_names,
    generate_factor_strategy_code,
    map_factor_direction,
    rank_factor_results,
    sort_symbols_by_volume,
)


def _build_candidate(factor_name: str, avg_ic_mean: float = 0.1, avg_icir: float = 1.0):
    return {
        "factor_name": factor_name,
        "direction": {"high_signal": "long", "low_signal": "short"},
        "thresholds": {"p20": 20.0, "p50": 50.0, "p80": 80.0},
        "avg_ic_mean": avg_ic_mean,
        "avg_icir": avg_icir,
    }


def test_return_over_drawdown_uses_floor_value():
    result = calculate_return_over_drawdown_score(
        total_pnl_percent=12.0,
        max_drawdown_percent=0.0,
        floor_value=1.0,
    )
    assert result == 12.0


def test_rank_factor_results_uses_tie_breakers():
    ranked = rank_factor_results([
        {
            "factor_name": "A",
            "score": 4.0,
            "sharpe_ratio": 1.1,
            "total_pnl_percent": 10.0,
            "total_trades": 20,
        },
        {
            "factor_name": "B",
            "score": 4.0,
            "sharpe_ratio": 1.4,
            "total_pnl_percent": 9.0,
            "total_trades": 10,
        },
    ])
    assert ranked[0]["factor_name"] == "B"


def test_collect_builtin_factor_names_includes_builtin_expression_rows():
    names = collect_builtin_factor_names(
        registry_names=["RSI14"],
        builtin_expression_names=["EMA_CROSS_7_21"],
    )
    assert names == ["EMA_CROSS_7_21", "RSI14"]


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


def test_resolve_top_hyperliquid_symbols_uses_batch_ticker_rows(monkeypatch):
    monkeypatch.setattr(
        factor_research_service_module,
        "get_all_ticker_data_from_hyperliquid",
        lambda environment="mainnet": [
            {"symbol": "DOGE", "volume24h": 5},
            {"symbol": "BTC", "volume24h": 20},
            {"symbol": "ETH", "volume24h": 10},
        ],
    )

    symbols = factor_research_service_module.resolve_top_hyperliquid_symbols(limit=2)

    assert symbols == ["BTC", "ETH"]


def test_map_factor_direction_positive_ic_is_trend_following():
    assert map_factor_direction(ic_value=0.12) == {
        "high_signal": "long",
        "low_signal": "short",
    }


def test_map_factor_direction_negative_ic_is_reversed():
    assert map_factor_direction(ic_value=-0.08) == {
        "high_signal": "short",
        "low_signal": "long",
    }


def test_build_percentile_thresholds_uses_20_50_80():
    thresholds = build_percentile_thresholds([1, 2, 3, 4, 5])

    assert thresholds == {"p20": 1.8, "p50": 3.0, "p80": 4.2}


def test_threshold_spread_score_penalizes_flat_thresholds():
    flat = calculate_threshold_spread_score({"p20": 100.0, "p50": 100.01, "p80": 100.02})
    wide = calculate_threshold_spread_score({"p20": 80.0, "p50": 100.0, "p80": 125.0})

    assert wide > flat
    assert flat < 0.05


def test_candidate_prescreen_score_rewards_coverage():
    lower_coverage = calculate_candidate_prescreen_score(
        avg_icir=1.2,
        avg_ic_mean=0.05,
        coverage_ratio=0.6,
        threshold_spread_score=0.3,
    )
    higher_coverage = calculate_candidate_prescreen_score(
        avg_icir=1.0,
        avg_ic_mean=0.04,
        coverage_ratio=1.0,
        threshold_spread_score=0.3,
    )

    assert higher_coverage > lower_coverage


def test_generate_factor_strategy_code_embeds_factor_details():
    code = generate_factor_strategy_code(
        factor_name="RSI14",
        period="1h",
        thresholds={"p20": 20.0, "p50": 50.0, "p80": 80.0},
        direction={"high_signal": "long", "low_signal": "short"},
        symbols=["BTC", "ETH"],
    )

    assert 'data.get_factor(symbol, "RSI14", period="1h")' in code
    assert 'symbols = ["BTC", "ETH"]' in code
    assert 'high_signal = "long"' in code


def test_generate_factor_strategy_code_uses_symbol_specific_thresholds_when_available():
    code = generate_factor_strategy_code(
        factor_name="RSI14",
        period="1h",
        thresholds={"p20": 20.0, "p50": 50.0, "p80": 80.0},
        thresholds_by_symbol={
            "BTC": {"p20": 10.0, "p50": 15.0, "p80": 25.0},
            "ETH": {"p20": 30.0, "p50": 45.0, "p80": 60.0},
        },
        direction={"high_signal": "long", "low_signal": "short"},
        symbols=["BTC", "ETH"],
    )

    assert 'thresholds_by_symbol = {' in code
    assert 'default_thresholds = {"p20": 20.0, "p50": 50.0, "p80": 80.0}' in code
    assert 'symbol_threshold = thresholds_by_symbol.get(symbol, default_thresholds)' in code
    assert 'symbol_p50 = symbol_threshold["p50"]' in code
    assert 'if value >= symbol_p80:' in code


def test_generate_factor_strategy_code_normalizes_cross_symbol_signal_strength():
    code = generate_factor_strategy_code(
        factor_name="RSI14",
        period="1h",
        thresholds={"p20": 20.0, "p50": 50.0, "p80": 80.0},
        thresholds_by_symbol={
            "BTC": {"p20": 10.0, "p50": 20.0, "p80": 30.0},
            "ETH": {"p20": 100.0, "p50": 130.0, "p80": 160.0},
        },
        direction={"high_signal": "long", "low_signal": "short"},
        symbols=["BTC", "ETH"],
    )

    assert 'symbol_span = max(abs(symbol_p80 - symbol_p20), 1e-09)' in code
    assert 'score = abs(value - symbol_p80) / symbol_span' in code
    assert 'score = abs(symbol_p20 - value) / symbol_span' in code


def test_build_research_backtest_config_is_scheduled_only():
    config = build_research_backtest_config(
        code="print('x')",
        symbols=["BTC", "ETH"],
        start_time_ms=1,
        end_time_ms=2,
    )

    assert config.signal_pool_ids == []
    assert config.scheduled_interval_sec == 3600
    assert config.preload_periods == ["1h"]
    assert config.intrabar_tp_sl_period is None


def test_build_factor_candidates_filters_low_quality_and_sorts_by_prescreen_score(monkeypatch):
    service = factor_research_service_module.FactorResearchService(db=object())
    symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TAO", "SUI", "XMR", "BNB", "PAXG"]
    factor_names = ["HIGH_COVER", "LOW_COVER", "FLAT_THRESHOLDS", "MID_COVER"]

    monkeypatch.setattr(
        service,
        "_load_effectiveness_summary",
        lambda **kwargs: {
            "HIGH_COVER": {
                "avg_ic_mean": 0.03,
                "avg_icir": 0.95,
                "symbols_with_effectiveness": 10,
            },
            "LOW_COVER": {
                "avg_ic_mean": 0.08,
                "avg_icir": 1.6,
                "symbols_with_effectiveness": 4,
            },
            "FLAT_THRESHOLDS": {
                "avg_ic_mean": 0.06,
                "avg_icir": 1.3,
                "symbols_with_effectiveness": 10,
            },
            "MID_COVER": {
                "avg_ic_mean": 0.04,
                "avg_icir": 1.05,
                "symbols_with_effectiveness": 7,
            },
        },
    )

    series_map = {
        "HIGH_COVER": [80, 90, 100, 110, 125],
        "LOW_COVER": [40, 60, 90, 120, 160],
        "FLAT_THRESHOLDS": [100.0, 100.01, 100.01, 100.02, 100.02],
        "MID_COVER": [90, 95, 100, 110, 118],
    }
    monkeypatch.setattr(
        service,
        "_load_factor_series_bundle",
        lambda **kwargs: series_map,
    )

    candidates = service.build_factor_candidates(
        exchange="hyperliquid",
        symbols=symbols,
        factor_names=factor_names,
        lookback_days=30,
        period="1h",
    )

    assert [row["factor_name"] for row in candidates] == ["HIGH_COVER", "MID_COVER"]
    assert candidates[0]["prescreen_score"] > candidates[1]["prescreen_score"]


def test_build_factor_candidates_uses_batched_series_loading(monkeypatch):
    service = factor_research_service_module.FactorResearchService(db=object())
    bundle_calls: list[dict] = []

    monkeypatch.setattr(
        service,
        "_load_effectiveness_summary",
        lambda **kwargs: {
            "RSI14": {
                "avg_ic_mean": 0.03,
                "avg_icir": 1.0,
                "symbols_with_effectiveness": 10,
            },
            "ROC10": {
                "avg_ic_mean": 0.04,
                "avg_icir": 0.9,
                "symbols_with_effectiveness": 10,
            },
        },
    )
    monkeypatch.setattr(
        service,
        "_load_factor_series_bundle",
        lambda **kwargs: bundle_calls.append(kwargs) or {
            "RSI14": [20, 30, 40, 50, 60],
            "ROC10": [10, 20, 40, 70, 110],
        },
    )

    candidates = service.build_factor_candidates(
        exchange="hyperliquid",
        symbols=["BTC", "ETH", "SOL", "XRP", "DOGE", "TAO", "SUI", "XMR", "BNB", "PAXG"],
        factor_names=["RSI14", "ROC10"],
        lookback_days=30,
        period="1h",
    )

    assert len(bundle_calls) == 1
    assert [row["factor_name"] for row in candidates] == ["ROC10", "RSI14"]


def test_build_factor_candidates_includes_symbol_specific_thresholds(monkeypatch):
    service = factor_research_service_module.FactorResearchService(db=object())

    monkeypatch.setattr(
        service,
        "_load_effectiveness_summary",
        lambda **kwargs: {
            "RSI14": {
                "avg_ic_mean": 0.03,
                "avg_icir": 1.0,
                "symbols_with_effectiveness": 10,
            },
        },
    )

    def _fake_load_factor_series_bundle(**kwargs):
        service._latest_factor_series_by_symbol_bundle = {
            "RSI14": {
                "BTC": [10, 20, 30, 40, 50],
                "ETH": [100, 110, 120, 130, 140],
            }
        }
        return {
            "RSI14": [10, 20, 30, 40, 50, 100, 110, 120, 130, 140],
        }

    monkeypatch.setattr(
        service,
        "_load_factor_series_bundle",
        _fake_load_factor_series_bundle,
    )

    candidates = service.build_factor_candidates(
        exchange="hyperliquid",
        symbols=["BTC", "ETH", "SOL", "XRP", "DOGE", "TAO", "SUI", "XMR", "BNB", "PAXG"],
        factor_names=["RSI14"],
        lookback_days=30,
        period="1h",
    )

    assert candidates[0]["thresholds_by_symbol"] == {
        "BTC": {"p20": 18.0, "p50": 30.0, "p80": 42.0},
        "ETH": {"p20": 108.0, "p50": 120.0, "p80": 132.0},
    }


def test_ensure_effectiveness_forwards_symbol_progress():
    progress_events: list[dict] = []

    class _DummyEffectivenessService:
        def __init__(self):
            self.callback = None

        def set_progress_callback(self, callback):
            self.callback = callback

        def compute_for_exchange(self, db, exchange, period="1h", force=False, symbols_override=None):
            self.callback(
                {
                    "status": "running",
                    "symbol_completed": 1,
                    "symbol_total": 2,
                    "current_symbol": "ETH",
                    "current_factor": "RSI14",
                    "factor_completed": 8,
                    "factor_total": 89,
                }
            )
            return {"computed": 42, "exchange": exchange}

    service = factor_research_service_module.FactorResearchService(
        db=object(),
        factor_effectiveness_service=_DummyEffectivenessService(),
    )
    service.set_progress_callback(progress_events.append)

    result = service.ensure_effectiveness(
        exchange="hyperliquid",
        symbols=["BTC", "ETH"],
        period="1h",
    )

    assert result == {"computed": 42, "exchange": "hyperliquid"}
    assert progress_events[-1]["phase"] == "ensure_effectiveness"
    assert progress_events[-1]["current_symbol"] == "ETH"
    assert progress_events[-1]["current_factor"] == "RSI14"
    assert progress_events[-1]["factor_total"] == 89


def test_build_staged_backtest_plan_prefers_fast_then_full_stage():
    plan = build_staged_backtest_plan(
        lookback_days=180,
        symbol_count=20,
        candidate_count=10,
    )

    assert plan == {
        "use_fast_stage": True,
        "fast_backtest_days": 45,
        "fast_symbol_count": 10,
        "full_backtest_limit": 3,
    }


def test_run_research_uses_fast_stage_before_full_backtest(monkeypatch):
    day_ms = 24 * 60 * 60 * 1000
    service = factor_research_service_module.FactorResearchService(
        db=object(),
        now_ms_factory=lambda: 180 * day_ms,
    )
    candidates = [
        _build_candidate("FACTOR_A", avg_ic_mean=0.02, avg_icir=0.7),
        _build_candidate("FACTOR_B", avg_ic_mean=0.03, avg_icir=0.9),
        _build_candidate("FACTOR_C", avg_ic_mean=0.04, avg_icir=1.1),
        _build_candidate("FACTOR_D", avg_ic_mean=0.05, avg_icir=0.8),
    ]
    symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TAO", "SUI", "XMR", "BNB", "PAXG", "LINK", "AAVE"]

    monkeypatch.setattr(service, "resolve_universe", lambda exchange, limit: symbols)
    monkeypatch.setattr(service, "collect_factor_names", lambda factor_scope: [row["factor_name"] for row in candidates])
    monkeypatch.setattr(service, "ensure_effectiveness", lambda exchange, resolved_symbols, period: None)
    monkeypatch.setattr(service, "build_factor_candidates", lambda **kwargs: list(candidates))

    calls: list[dict] = []

    def fake_backtest_factor(candidate, symbols, start_time_ms, end_time_ms, exchange, period):
        lookback_days = int((end_time_ms - start_time_ms) / day_ms)
        calls.append(
            {
                "factor_name": candidate["factor_name"],
                "symbols": list(symbols),
                "lookback_days": lookback_days,
            }
        )
        if lookback_days < 180:
            fast_scores = {
                "FACTOR_A": 0.8,
                "FACTOR_B": 2.3,
                "FACTOR_C": 1.9,
                "FACTOR_D": 1.2,
            }
            score = fast_scores[candidate["factor_name"]]
            return {
                **candidate,
                "score": score,
                "total_pnl_percent": score * 5,
                "max_drawdown_percent": 5.0,
                "sharpe_ratio": score,
                "total_trades": 10,
                "symbols_tested": len(symbols),
                "success": True,
            }

        full_scores = {
            "FACTOR_A": 0.5,
            "FACTOR_B": 1.8,
            "FACTOR_C": 2.6,
            "FACTOR_D": 0.9,
        }
        score = full_scores[candidate["factor_name"]]
        return {
            **candidate,
            "score": score,
            "total_pnl_percent": score * 6,
            "max_drawdown_percent": 4.0,
            "sharpe_ratio": score,
            "total_trades": 20,
            "symbols_tested": len(symbols),
            "success": True,
        }

    monkeypatch.setattr(service, "backtest_factor", fake_backtest_factor)

    result = service.run_research(
        exchange="hyperliquid",
        top_n_symbols=20,
        lookback_days=180,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
        prescreen_limit=10,
    )

    assert [row["factor_name"] for row in result["ranked_results"]] == [
        "FACTOR_C",
        "FACTOR_B",
        "FACTOR_D",
    ]
    assert result["top_factor"]["factor_name"] == "FACTOR_C"
    assert result["candidate_count"] == 4
    assert result["fast_candidate_count"] == 4
    assert result["full_backtest_candidate_count"] == 3
    assert result["fast_backtest_days"] == 45
    assert result["fast_backtest_symbol_count"] == 10
    assert [row["factor_name"] for row in result["fast_ranked_results"]] == [
        "FACTOR_B",
        "FACTOR_C",
        "FACTOR_D",
    ]
    assert result["portfolio_ranked_results"]
    assert result["top_portfolio"] is not None
    assert result["top_portfolio"]["construction_method"] in {
        "equal_weight_top_n",
        "score_weighted_top_n",
        "category_balanced_weighted",
    }

    assert [call["factor_name"] for call in calls[:4]] == [
        "FACTOR_A",
        "FACTOR_B",
        "FACTOR_C",
        "FACTOR_D",
    ]
    assert all(call["lookback_days"] == 45 for call in calls[:4])
    assert all(len(call["symbols"]) == 10 for call in calls[:4])
    assert [call["factor_name"] for call in calls[4:]] == [
        "FACTOR_B",
        "FACTOR_C",
        "FACTOR_D",
    ]
    assert all(call["lookback_days"] == 180 for call in calls[4:])
    assert all(len(call["symbols"]) == len(symbols) for call in calls[4:])


def test_run_research_emits_progress_updates(monkeypatch):
    service = factor_research_service_module.FactorResearchService(db=object())
    candidates = [
        _build_candidate("FACTOR_A"),
        _build_candidate("FACTOR_B"),
        _build_candidate("FACTOR_C"),
        _build_candidate("FACTOR_D"),
    ]
    progress_events: list[dict] = []
    service.set_progress_callback(progress_events.append)

    monkeypatch.setattr(service, "resolve_universe", lambda exchange, limit: ["BTC", "ETH", "SOL", "XRP"])
    monkeypatch.setattr(service, "collect_factor_names", lambda factor_scope: [row["factor_name"] for row in candidates])
    monkeypatch.setattr(service, "ensure_effectiveness", lambda exchange, symbols, period: None)
    monkeypatch.setattr(service, "build_factor_candidates", lambda **kwargs: list(candidates))
    monkeypatch.setattr(
        service,
        "backtest_factor",
        lambda candidate, symbols, start_time_ms, end_time_ms, exchange, period: {
            **candidate,
            "score": {"FACTOR_A": 0.8, "FACTOR_B": 2.1, "FACTOR_C": 1.7, "FACTOR_D": 1.1}[candidate["factor_name"]],
            "total_pnl_percent": 8.0,
            "max_drawdown_percent": 4.0,
            "sharpe_ratio": 1.0,
            "total_trades": 10,
            "symbols_tested": len(symbols),
            "success": True,
        },
    )

    result = service.run_research(
        exchange="hyperliquid",
        top_n_symbols=4,
        lookback_days=180,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
        prescreen_limit=10,
    )

    phases = [event["phase"] for event in progress_events]
    assert phases[0] == "preparing"
    assert "candidate_prescreen" in phases
    assert "fast_backtest" in phases
    assert "full_backtest" in phases
    assert phases[-1] == "complete"
    assert progress_events[-1]["candidate_count"] == 4
    assert progress_events[-1]["full_backtest_candidate_count"] == 3
    assert progress_events[-1]["current_factor"] == result["top_factor"]["factor_name"]


def test_run_research_returns_auto_live_decision_when_enabled(monkeypatch):
    service = factor_research_service_module.FactorResearchService(db=object())
    candidate = _build_candidate("FACTOR_A")

    monkeypatch.setattr(service, "resolve_universe", lambda exchange, limit: ["BTC", "ETH"])
    monkeypatch.setattr(service, "collect_factor_names", lambda factor_scope: ["FACTOR_A"])
    monkeypatch.setattr(service, "ensure_effectiveness", lambda exchange, symbols, period: None)
    monkeypatch.setattr(service, "build_factor_candidates", lambda **kwargs: [candidate])
    monkeypatch.setattr(
        service,
        "backtest_factor",
        lambda candidate, symbols, start_time_ms, end_time_ms, exchange, period: {
            **candidate,
            "score": 2.1,
            "total_pnl_percent": 12.0,
            "max_drawdown_percent": 4.0,
            "sharpe_ratio": 1.2,
            "total_trades": 15,
            "symbols_tested": len(symbols),
            "success": True,
        },
    )
    monkeypatch.setattr(
        service,
        "_persist_research_run",
        lambda run_config, result: (
            123,
            [
                {
                    **(result.get("top_portfolio") or {}),
                    "portfolio_id": 42,
                    "run_id": 123,
                }
            ],
            {
                **(result.get("top_portfolio") or {}),
                "portfolio_id": 42,
                "run_id": 123,
            },
        ),
    )

    import services.factor_portfolio_deployment_service as deployment_module

    captured: dict[str, dict] = {}

    def _fake_deploy_portfolio_candidate(db, **kwargs):
        captured["paper"] = kwargs
        return {
            "deployment": {"id": 3001, "mode": "paper", "status": "deployed"},
        }

    def _fake_auto_decide_live_promotion(db, **kwargs):
        captured["live"] = kwargs
        return {
            "decision": "promoted",
            "reason": "gate_passed",
            "gate": {"passed": True, "failed_checks": [], "checks": {}},
            "paper_context": {"paper_account_id": kwargs["paper_account_id"]},
            "live_deployment": {
                "deployment": {"id": 4001, "mode": "live", "status": "deployed"},
            },
        }

    monkeypatch.setattr(
        deployment_module,
        "deploy_portfolio_candidate",
        _fake_deploy_portfolio_candidate,
    )
    monkeypatch.setattr(
        deployment_module,
        "auto_decide_live_promotion",
        _fake_auto_decide_live_promotion,
    )

    result = service.run_research(
        exchange="hyperliquid",
        top_n_symbols=2,
        lookback_days=30,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
        period="1h",
        prescreen_limit=1,
        auto_promote_paper=True,
        paper_account_id=7,
        auto_promote_live=True,
        live_account_id=8,
        live_min_observation_hours=12.0,
        live_min_trades=5,
        live_min_net_pnl=10.0,
        live_min_win_rate=55.0,
        live_max_drawdown_percent=15.0,
    )

    assert result["auto_paper_deployment"]["deployment"]["mode"] == "paper"
    assert result["auto_live_decision"]["decision"] == "promoted"
    assert captured["paper"]["portfolio_id"] == 42
    assert captured["live"]["portfolio_id"] == 42
    assert captured["live"]["paper_account_id"] == 7
    assert captured["live"]["live_account_id"] == 8
    assert captured["live"]["min_observation_hours"] == 12.0
    assert captured["live"]["min_trades"] == 5
    assert captured["live"]["min_net_pnl"] == 10.0
    assert captured["live"]["min_win_rate"] == 55.0
    assert captured["live"]["max_drawdown_percent_limit"] == 15.0
    assert captured["live"]["paper_deployment_id"] == 3001


def test_factor_research_automation_service_start_registers_interval_task():
    assert hasattr(factor_research_service_module, "FactorResearchAutomationService")

    class _DummyScheduler:
        def __init__(self):
            self.removed = []
            self.added = []

        def remove_task(self, task_id):
            self.removed.append(task_id)

        def add_interval_task(self, task_func, interval_seconds, task_id, *args, **kwargs):
            self.added.append(
                {
                    "task_func": task_func,
                    "interval_seconds": interval_seconds,
                    "task_id": task_id,
                }
            )

    scheduler = _DummyScheduler()
    service = factor_research_service_module.FactorResearchAutomationService(
        scheduler=scheduler,
        session_factory=lambda: object(),
        research_service_factory=lambda db: object(),
    )

    service.start(interval_seconds=900, top_n_symbols=20, lookback_days=180)

    assert scheduler.removed == [service.TASK_ID]
    assert scheduler.added[0]["task_func"] == service._run
    assert scheduler.added[0]["interval_seconds"] == 900
    assert scheduler.added[0]["task_id"] == service.TASK_ID
    assert service.get_status()["config"]["lookback_days"] == 180


def test_factor_research_automation_service_hydrates_latest_success_from_db():
    assert hasattr(factor_research_service_module, "FactorResearchAutomationService")

    class _DummyScheduler:
        def remove_task(self, task_id):
            return None

        def add_interval_task(self, task_func, interval_seconds, task_id, *args, **kwargs):
            return None

    class _RunRow:
        def __init__(self):
            self.id = 99
            self.exchange = "hyperliquid"
            self.top_n_symbols = 20
            self.lookback_days = 180
            self.objective = "return_over_drawdown"
            self.factor_scope = "builtin_only"
            self.period = "1h"
            self.prescreen_limit = 10
            self.status = "success"
            self.result_json = (
                '{"symbols":["BTC","ETH"],'
                '"candidate_count":3,'
                '"full_backtest_candidate_count":2,'
                '"top_factor":{"factor_name":"ATR_RATIO","score":2.4}}'
            )
            self.top_factor_json = '{"factor_name":"ATR_RATIO","score":2.4}'
            self.top_portfolio_json = '{"name":"Top Portfolio","portfolio_id":123}'
            self.started_at = datetime.now(timezone.utc)
            self.completed_at = datetime.now(timezone.utc)
            self.created_at = datetime.now(timezone.utc)

    class _DummyQuery:
        def __init__(self, row):
            self._row = row

        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def first(self):
            return self._row

    class _DummyDb:
        def __init__(self, row):
            self._row = row
            self.closed = False

        def query(self, *_args, **_kwargs):
            return _DummyQuery(self._row)

        def close(self):
            self.closed = True

    db = _DummyDb(_RunRow())
    service = factor_research_service_module.FactorResearchAutomationService(
        scheduler=_DummyScheduler(),
        session_factory=lambda: db,
        research_service_factory=lambda _db: object(),
    )

    status = service.get_status()

    assert status["status"] == "idle"
    assert status["last_run_status"] == "success"
    assert status["config"]["lookback_days"] == 180
    assert status["last_result"]["symbols"] == ["BTC", "ETH"]
    assert status["last_top_factor"]["factor_name"] == "ATR_RATIO"
    assert status["last_top_portfolio"]["portfolio_id"] == 123
    assert status["progress"]["phase"] == "complete"
    assert db.closed is True


def test_factor_research_automation_service_run_now_tracks_last_result():
    assert hasattr(factor_research_service_module, "FactorResearchAutomationService")

    class _DummyScheduler:
        def remove_task(self, task_id):
            return None

        def add_interval_task(self, task_func, interval_seconds, task_id, *args, **kwargs):
            return None

    class _DummyDb:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class _DummyResearchService:
        def __init__(self, db):
            self.db = db

        def run_research(self, **kwargs):
            return {
                "symbols": ["BTC", "ETH"],
                "ranked_results": [{"factor_name": "ATR_RATIO", "score": 2.4}],
                "top_factor": {"factor_name": "ATR_RATIO", "score": 2.4},
                **kwargs,
            }

    db = _DummyDb()
    service = factor_research_service_module.FactorResearchAutomationService(
        scheduler=_DummyScheduler(),
        session_factory=lambda: db,
        research_service_factory=_DummyResearchService,
    )

    result = service.run_now(top_n_symbols=20, lookback_days=180)
    status = service.get_status()

    assert result["top_factor"]["factor_name"] == "ATR_RATIO"
    assert status["last_run_status"] == "success"
    assert status["last_top_factor"]["factor_name"] == "ATR_RATIO"
    assert status["last_result"]["symbols"] == ["BTC", "ETH"]
    assert db.closed is True


def test_factor_research_automation_service_trigger_run_updates_status_in_background():
    assert hasattr(factor_research_service_module, "FactorResearchAutomationService")

    class _DummyScheduler:
        def remove_task(self, task_id):
            return None

        def add_interval_task(self, task_func, interval_seconds, task_id, *args, **kwargs):
            return None

    class _DummyDb:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class _DummyResearchService:
        def __init__(self, db):
            self.db = db
            self.progress_callback = None

        def set_progress_callback(self, callback):
            self.progress_callback = callback

        def run_research(self, **kwargs):
            if self.progress_callback is not None:
                self.progress_callback(
                    {
                        "phase": "fast_backtest",
                        "current": 1,
                        "total": 3,
                        "current_factor": "ATR_RATIO",
                    }
                )
            time.sleep(0.05)
            return {
                "symbols": ["BTC", "ETH"],
                "ranked_results": [{"factor_name": "ATR_RATIO", "score": 2.4}],
                "top_factor": {"factor_name": "ATR_RATIO", "score": 2.4},
                **kwargs,
            }

    db = _DummyDb()
    service = factor_research_service_module.FactorResearchAutomationService(
        scheduler=_DummyScheduler(),
        session_factory=lambda: db,
        research_service_factory=_DummyResearchService,
    )

    response = service.trigger_run(top_n_symbols=20, lookback_days=180)
    started_status = service.get_status()

    assert response["status"] == "started"
    assert started_status["status"] == "running"
    assert started_status["last_run_status"] == "running"
    assert started_status["progress"]["phase"] == "queued"

    deadline = time.time() + 1.0
    while time.time() < deadline:
        status = service.get_status()
        if status["progress"]["phase"] == "fast_backtest":
            break
        time.sleep(0.02)

    running_status = service.get_status()
    assert running_status["progress"]["phase"] in {"fast_backtest", "complete"}

    deadline = time.time() + 1.0
    while time.time() < deadline:
        status = service.get_status()
        if status["last_run_status"] == "success":
            break
        time.sleep(0.02)

    final_status = service.get_status()
    assert final_status["status"] == "idle"
    assert final_status["last_run_status"] == "success"
    assert final_status["last_top_factor"]["factor_name"] == "ATR_RATIO"
    assert final_status["last_result"]["symbols"] == ["BTC", "ETH"]
    assert final_status["progress"]["phase"] == "complete"
    assert db.closed is True
