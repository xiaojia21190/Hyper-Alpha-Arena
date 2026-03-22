from repositories import kline_repo as kline_repo_module
from services import factor_data_provider as factor_data_provider_module
from services import hyperliquid_market_data as hyperliquid_market_data_module


class _DummyExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _DummyDb:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *args, **kwargs):
        return _DummyExecuteResult(self._rows)


def test_get_klines_from_db_defaults_null_volume_to_zero():
    klines = factor_data_provider_module.get_klines_from_db(
        _DummyDb([(1, 2, 3, 4, 5, None)]),
        exchange="hyperliquid",
        symbol="BTC",
        period="1h",
    )

    assert klines == [
        {
            "timestamp": 1,
            "open": 2.0,
            "high": 3.0,
            "low": 4.0,
            "close": 5.0,
            "volume": 0.0,
        }
    ]


def test_backfill_hyperliquid_uses_current_db_session(monkeypatch):
    captured = {"save_calls": []}

    class _DummyRepo:
        def __init__(self, db):
            captured["repo_db"] = db

        def save_kline_data(self, **kwargs):
            captured["save_calls"].append(kwargs)
            return {"total": 1}

    monkeypatch.setattr(
        hyperliquid_market_data_module,
        "get_kline_data_from_hyperliquid",
        lambda symbol, period, count, persist: [
            {
                "timestamp": 1,
                "datetime": "2026-01-01T00:00:00+00:00",
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
                "amount": 1.0,
                "chg": 0.0,
                "percent": 0.0,
            }
        ],
    )
    monkeypatch.setattr(kline_repo_module, "KlineRepository", _DummyRepo)

    db = object()
    factor_data_provider_module._backfill_hyperliquid(db, "BTC", "1h", 2000)

    assert captured["repo_db"] is db
    assert captured["save_calls"][0]["symbol"] == "BTC"
    assert captured["save_calls"][0]["exchange"] == "hyperliquid"
