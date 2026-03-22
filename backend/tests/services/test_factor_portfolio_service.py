from services.factor_portfolio_service import (
    build_portfolio_candidates,
    pick_recommended_portfolio,
    rank_portfolio_candidates,
)


def _factor_row(
    name: str,
    score: float,
    category: str,
    sharpe_ratio: float = 1.0,
    pnl: float = 10.0,
    drawdown: float = 5.0,
):
    return {
        "factor_name": name,
        "score": score,
        "category": category,
        "sharpe_ratio": sharpe_ratio,
        "total_pnl_percent": pnl,
        "max_drawdown_percent": drawdown,
        "total_trades": 20,
    }


def test_build_portfolio_candidates_returns_expected_methods():
    factors = [
        _factor_row("RSI14", 2.1, "momentum"),
        _factor_row("ATR_RATIO", 1.8, "volatility"),
        _factor_row("VOL_Z", 1.6, "volume"),
        _factor_row("EMA_CROSS", 1.2, "trend"),
    ]
    candidates = build_portfolio_candidates(factors, top_n=4)
    methods = {row["construction_method"] for row in candidates}

    assert methods == {
        "equal_weight_top_n",
        "score_weighted_top_n",
        "category_balanced_weighted",
    }
    for candidate in candidates:
        total_weight = round(sum(component["weight"] for component in candidate["weights"]), 6)
        assert total_weight == 1.0


def test_rank_and_recommend_portfolio_candidates():
    factors = [
        _factor_row("FACTOR_A", 2.4, "momentum", sharpe_ratio=1.3, pnl=12.0, drawdown=4.0),
        _factor_row("FACTOR_B", 1.9, "volatility", sharpe_ratio=1.1, pnl=10.0, drawdown=5.0),
        _factor_row("FACTOR_C", 1.7, "volume", sharpe_ratio=0.9, pnl=8.0, drawdown=4.0),
    ]
    candidates = build_portfolio_candidates(factors, top_n=3)
    ranked = rank_portfolio_candidates(candidates)
    recommended = pick_recommended_portfolio(candidates)

    assert ranked[0]["score"] >= ranked[-1]["score"]
    assert recommended is not None
    assert recommended["name"] == ranked[0]["name"]
    assert recommended["rationale"]["component_count"] == ranked[0]["component_count"]

