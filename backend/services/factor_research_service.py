from __future__ import annotations


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
