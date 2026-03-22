from services.factor_research_service import FactorResearchService


def test_run_research_returns_ranked_results_for_small_fixture(monkeypatch):
    service = FactorResearchService(db=object())

    monkeypatch.setattr(service, "resolve_universe", lambda exchange, limit: ["BTC", "ETH"])
    monkeypatch.setattr(service, "collect_factor_names", lambda factor_scope: ["FACTOR_A", "FACTOR_B"])
    monkeypatch.setattr(service, "ensure_effectiveness", lambda exchange, symbols, period: None)
    monkeypatch.setattr(
        service,
        "build_factor_candidates",
        lambda exchange, symbols, factor_names, lookback_days, period: [
            {
                "factor_name": "FACTOR_A",
                "direction": {"high_signal": "long", "low_signal": "short"},
                "thresholds": {"p20": 20.0, "p50": 50.0, "p80": 80.0},
                "avg_ic_mean": 0.1,
                "avg_icir": 0.4,
            },
            {
                "factor_name": "FACTOR_B",
                "direction": {"high_signal": "short", "low_signal": "long"},
                "thresholds": {"p20": 10.0, "p50": 40.0, "p80": 70.0},
                "avg_ic_mean": -0.2,
                "avg_icir": 0.6,
            },
        ],
    )

    def fake_backtest_factor(candidate, symbols, start_time_ms, end_time_ms, exchange, period):
        if candidate["factor_name"] == "FACTOR_A":
            return {
                "factor_name": "FACTOR_A",
                "score": 1.0,
                "total_pnl_percent": 8.0,
                "max_drawdown_percent": 8.0,
                "sharpe_ratio": 1.0,
                "total_trades": 12,
            }

        return {
            "factor_name": "FACTOR_B",
            "score": 2.5,
            "total_pnl_percent": 10.0,
            "max_drawdown_percent": 4.0,
            "sharpe_ratio": 1.4,
            "total_trades": 18,
        }

    monkeypatch.setattr(service, "backtest_factor", fake_backtest_factor)

    result = service.run_research(
        exchange="hyperliquid",
        top_n_symbols=2,
        lookback_days=14,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
    )

    assert result["top_factor"]["factor_name"] == "FACTOR_B"
    assert [row["factor_name"] for row in result["ranked_results"]] == ["FACTOR_B", "FACTOR_A"]
    assert result["symbols"] == ["BTC", "ETH"]
    assert result["top_portfolio"] is not None
    assert len(result["portfolio_ranked_results"]) >= 1
