from services import technical_indicators as technical_indicators_module


def test_calculate_indicators_returns_empty_when_pandas_ta_unavailable(monkeypatch):
    monkeypatch.setattr(
        technical_indicators_module,
        "PANDAS_TA_AVAILABLE",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        technical_indicators_module,
        "PANDAS_TA_IMPORT_ERROR",
        ModuleNotFoundError("mock missing pandas_ta backend"),
        raising=False,
    )

    payload = [
        {
            "timestamp": 1,
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "volume": 1,
        }
    ]
    assert technical_indicators_module.calculate_indicators(payload, ["RSI14"]) == {}

