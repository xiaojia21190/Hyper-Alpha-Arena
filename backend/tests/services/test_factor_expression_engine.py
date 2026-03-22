from services.factor_expression_engine import FactorExpressionEngine


def test_execute_returns_error_when_ta_functions_unavailable(monkeypatch):
    engine = FactorExpressionEngine()

    def _raise(_df):
        raise ModuleNotFoundError("mock pandas_ta backend missing")

    monkeypatch.setattr(engine, "_build_functions", _raise)

    klines = []
    for i in range(12):
        klines.append(
            {
                "timestamp": i + 1,
                "open": 100 + i,
                "high": 101 + i,
                "low": 99 + i,
                "close": 100 + i,
                "volume": 1000 + i,
            }
        )

    series, err = engine.execute("close", klines)
    assert series is None
    assert "TA functions unavailable" in err
