from __future__ import annotations

import math
from typing import Any


def _normalize_weights(weights: list[float]) -> list[float]:
    cleaned = [max(float(weight), 0.0) for weight in weights]
    total = sum(cleaned)
    if total <= 0:
        if not cleaned:
            return []
        uniform = 1.0 / len(cleaned)
        return [round(uniform, 6) for _ in cleaned]
    return [round(weight / total, 6) for weight in cleaned]


def _component_from_row(row: dict[str, Any], weight: float) -> dict[str, Any]:
    return {
        "factor_name": row.get("factor_name"),
        "category": row.get("category", "uncategorized"),
        "weight": round(float(weight), 6),
        "factor_score": float(row.get("score", row.get("research_score", 0.0)) or 0.0),
        "sharpe_ratio": float(row.get("sharpe_ratio", 0.0) or 0.0),
        "total_pnl_percent": float(row.get("total_pnl_percent", 0.0) or 0.0),
        "max_drawdown_percent": float(row.get("max_drawdown_percent", 0.0) or 0.0),
        "total_trades": int(row.get("total_trades", 0) or 0),
    }


def _weighted_metric(components: list[dict[str, Any]], key: str) -> float:
    return round(
        sum(float(component.get("weight", 0.0)) * float(component.get(key, 0.0)) for component in components),
        6,
    )


def score_portfolio_candidate(candidate: dict[str, Any], objective: str = "return_over_drawdown") -> float:
    components = candidate.get("weights", [])
    if not components:
        return float("-inf")

    weighted_pnl = _weighted_metric(components, "total_pnl_percent")
    weighted_drawdown = abs(_weighted_metric(components, "max_drawdown_percent"))
    weighted_sharpe = _weighted_metric(components, "sharpe_ratio")
    weighted_factor_score = _weighted_metric(components, "factor_score")

    if objective == "return_over_drawdown":
        risk_adjusted = weighted_pnl / max(weighted_drawdown, 1.0)
    else:
        risk_adjusted = weighted_factor_score

    categories = {component.get("category", "uncategorized") for component in components}
    diversification_bonus = min(len(categories), 5) * 0.03
    sharpe_bonus = min(max(weighted_sharpe, 0.0), 3.0) * 0.2
    return round(risk_adjusted + diversification_bonus + sharpe_bonus, 6)


def rank_portfolio_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda row: (
            row.get("score", float("-inf")),
            row.get("weighted_sharpe_ratio", float("-inf")),
            row.get("weighted_total_pnl_percent", float("-inf")),
            row.get("component_count", 0),
            row.get("construction_method", ""),
        ),
        reverse=True,
    )


def pick_recommended_portfolio(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    best = rank_portfolio_candidates(candidates)[0]
    return {
        **best,
        "rationale": {
            "summary": "highest portfolio score with risk-adjusted return and diversification",
            "construction_method": best.get("construction_method"),
            "component_count": best.get("component_count", 0),
        },
    }


def build_portfolio_candidates(
    factor_rows: list[dict[str, Any]],
    top_n: int = 5,
    objective: str = "return_over_drawdown",
) -> list[dict[str, Any]]:
    if not factor_rows:
        return []

    ranked_rows = sorted(
        factor_rows,
        key=lambda row: (
            float(row.get("score", row.get("research_score", float("-inf")))),
            float(row.get("sharpe_ratio", float("-inf"))),
            row.get("factor_name", ""),
        ),
        reverse=True,
    )
    selected = ranked_rows[: max(1, min(top_n, len(ranked_rows)))]
    candidates: list[dict[str, Any]] = []

    # Candidate 1: Equal weight among top-N factors.
    equal_weights = _normalize_weights([1.0 for _ in selected])
    equal_components = [
        _component_from_row(row, weight) for row, weight in zip(selected, equal_weights)
    ]
    equal_candidate = {
        "id": 1,
        "name": "equal_weight_top_n",
        "construction_method": "equal_weight_top_n",
        "weights": equal_components,
        "component_count": len(equal_components),
    }
    equal_candidate["weighted_total_pnl_percent"] = _weighted_metric(equal_components, "total_pnl_percent")
    equal_candidate["weighted_max_drawdown_percent"] = _weighted_metric(equal_components, "max_drawdown_percent")
    equal_candidate["weighted_sharpe_ratio"] = _weighted_metric(equal_components, "sharpe_ratio")
    equal_candidate["score"] = score_portfolio_candidate(equal_candidate, objective=objective)
    candidates.append(equal_candidate)

    # Candidate 2: Score-weighted top-N factors.
    raw_scores = [max(float(row.get("score", row.get("research_score", 0.0)) or 0.0), 0.0) for row in selected]
    score_weights = _normalize_weights(raw_scores)
    score_components = [
        _component_from_row(row, weight) for row, weight in zip(selected, score_weights)
    ]
    score_candidate = {
        "id": 2,
        "name": "score_weighted_top_n",
        "construction_method": "score_weighted_top_n",
        "weights": score_components,
        "component_count": len(score_components),
    }
    score_candidate["weighted_total_pnl_percent"] = _weighted_metric(score_components, "total_pnl_percent")
    score_candidate["weighted_max_drawdown_percent"] = _weighted_metric(score_components, "max_drawdown_percent")
    score_candidate["weighted_sharpe_ratio"] = _weighted_metric(score_components, "sharpe_ratio")
    score_candidate["score"] = score_portfolio_candidate(score_candidate, objective=objective)
    candidates.append(score_candidate)

    # Candidate 3: Category-balanced one-best-per-category with equal weights.
    best_by_category: dict[str, dict[str, Any]] = {}
    for row in selected:
        category = str(row.get("category", "uncategorized"))
        current = best_by_category.get(category)
        row_score = float(row.get("score", row.get("research_score", float("-inf"))))
        if current is None:
            best_by_category[category] = row
            continue
        current_score = float(current.get("score", current.get("research_score", float("-inf"))))
        if row_score > current_score:
            best_by_category[category] = row

    balanced_rows = list(best_by_category.values())
    balanced_weights = _normalize_weights([1.0 for _ in balanced_rows])
    balanced_components = [
        _component_from_row(row, weight) for row, weight in zip(balanced_rows, balanced_weights)
    ]
    balanced_candidate = {
        "id": 3,
        "name": "category_balanced_weighted",
        "construction_method": "category_balanced_weighted",
        "weights": balanced_components,
        "component_count": len(balanced_components),
    }
    balanced_candidate["weighted_total_pnl_percent"] = _weighted_metric(balanced_components, "total_pnl_percent")
    balanced_candidate["weighted_max_drawdown_percent"] = _weighted_metric(
        balanced_components, "max_drawdown_percent"
    )
    balanced_candidate["weighted_sharpe_ratio"] = _weighted_metric(balanced_components, "sharpe_ratio")
    balanced_candidate["score"] = score_portfolio_candidate(balanced_candidate, objective=objective)
    candidates.append(balanced_candidate)

    return rank_portfolio_candidates(candidates)


def build_weighted_portfolio_strategy_code(
    candidate: dict[str, Any],
    period: str = "1h",
    entry_threshold: float = 0.35,
    exit_threshold: float = 0.1,
) -> str:
    components = candidate.get("weights", [])
    if not components:
        raise ValueError("Portfolio candidate has no components")

    component_rows: list[dict[str, Any]] = []
    for component in components:
        factor_name = str(component.get("factor_name", "")).strip()
        if not factor_name:
            continue
        weight = float(component.get("weight", 0.0) or 0.0)
        if math.isnan(weight) or math.isinf(weight):
            continue
        component_rows.append({"factor_name": factor_name, "weight": round(weight, 6)})

    if not component_rows:
        raise ValueError("Portfolio candidate has no valid factor components")

    components_literal = str(component_rows).replace("'", '"')
    return f"""
class WeightedFactorPortfolioStrategy:
    def should_trade(self, data):
        components = {components_literal}
        score_by_symbol = {{}}
        for symbol in data.symbols:
            agg_score = 0.0
            valid_count = 0
            for component in components:
                factor = data.get_factor(symbol, component["factor_name"], period="{period}")
                value = factor.get("value") if factor else None
                if value is None:
                    continue
                agg_score += float(value) * float(component["weight"])
                valid_count += 1

            if valid_count > 0:
                score_by_symbol[symbol] = agg_score

        if not score_by_symbol:
            fallback_symbol = data.trigger_symbol or (data.symbols[0] if data.symbols else "")
            return Decision(operation="hold", symbol=fallback_symbol, reason="No factor data available")

        target_symbol, target_score = max(score_by_symbol.items(), key=lambda x: abs(x[1]))
        position = data.positions.get(target_symbol)
        price = data.get_price(target_symbol)
        if price <= 0:
            return Decision(operation="hold", symbol=target_symbol, reason="Price unavailable")

        if position:
            if abs(target_score) <= {exit_threshold}:
                return Decision(
                    operation="close",
                    symbol=target_symbol,
                    target_portion_of_balance=1.0,
                    leverage=1,
                    reason="Portfolio score mean reversion exit",
                )
            return Decision(operation="hold", symbol=target_symbol, reason="Keep current position")

        if target_score >= {entry_threshold}:
            return Decision(
                operation="buy",
                symbol=target_symbol,
                target_portion_of_balance=0.25,
                leverage=2,
                max_price=price * 1.001,
                reason="Portfolio weighted factor long signal",
            )
        if target_score <= -{entry_threshold}:
            return Decision(
                operation="sell",
                symbol=target_symbol,
                target_portion_of_balance=0.25,
                leverage=2,
                min_price=price * 0.999,
                reason="Portfolio weighted factor short signal",
            )
        return Decision(operation="hold", symbol=target_symbol, reason="Portfolio score below entry threshold")
""".strip()

