import pandas as pd

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


def test_calculate_indicators_sorts_timestamp_for_vwap(monkeypatch):
    class _DummyTA:
        @staticmethod
        def vwap(high, low, close, volume):
            assert isinstance(high.index, pd.DatetimeIndex)
            assert high.index.is_monotonic_increasing
            # Return deterministic values in sorted-timestamp order.
            return pd.Series([1.0, 2.0, 3.0], index=high.index)

    monkeypatch.setattr(
        technical_indicators_module,
        "PANDAS_TA_AVAILABLE",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        technical_indicators_module,
        "ta",
        _DummyTA(),
        raising=False,
    )

    payload = [
        {"timestamp": 3, "open": 1, "high": 3, "low": 1, "close": 2, "volume": 100},
        {"timestamp": 1, "open": 1, "high": 3, "low": 1, "close": 2, "volume": 100},
        {"timestamp": 2, "open": 1, "high": 3, "low": 1, "close": 2, "volume": 100},
    ]

    result = technical_indicators_module.calculate_indicators(payload, ["VWAP"])

    assert result["VWAP"] == [1.0, 2.0, 3.0]
