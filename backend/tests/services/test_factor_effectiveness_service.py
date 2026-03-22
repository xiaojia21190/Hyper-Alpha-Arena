from datetime import datetime, timedelta, timezone

from services import factor_effectiveness_service as factor_effectiveness_service_module
from services.factor_effectiveness_service import FactorEffectivenessService


class _DummyDb:
    def commit(self):
        return None


def test_normalize_symbols_override_deduplicates_and_uppercases():
    service = FactorEffectivenessService()

    symbols = service._normalize_symbols_override(["BTC", " eth ", "btc", "", None, "ETH"])

    assert symbols == ["BTC", "ETH"]


def test_compute_for_exchange_prefers_symbols_override(monkeypatch):
    service = FactorEffectivenessService()
    seen_symbols = []

    monkeypatch.setattr(service, "_get_symbols", lambda db, exchange: ["WATCHLIST_ONLY"])

    def fake_compute_symbol(db, exchange, symbol, period, force=False):
        seen_symbols.append(symbol)
        return 0

    monkeypatch.setattr(service, "_compute_symbol", fake_compute_symbol)

    result = service.compute_for_exchange(
        _DummyDb(),
        "hyperliquid",
        symbols_override=["BTC", "ETH", "btc"],
    )

    assert seen_symbols == ["BTC", "ETH"]
    assert result == {"computed": 0, "exchange": "hyperliquid"}


def test_symbol_effectiveness_freshness_requires_latest_date_and_full_factor_count():
    service = FactorEffectivenessService()

    class _Result:
        def __init__(self, row):
            self._row = row

        def fetchone(self):
            return self._row

    class _DummyDb:
        def __init__(self, latest_row, historical_count):
            self.latest_row = latest_row
            self.historical_count = historical_count

        def execute(self, statement, params=None):
            sql = str(statement)
            if "GROUP BY calc_date" in sql:
                return _Result(self.latest_row)
            return _Result((self.historical_count,))

    latest_calc_date = datetime(2026, 3, 21, tzinfo=timezone.utc).date()

    assert service._is_symbol_effectiveness_fresh(
        _DummyDb((latest_calc_date.isoformat(), 89), 89),
        exchange="hyperliquid",
        symbol="BTC",
        period="1h",
        latest_calc_date=latest_calc_date,
        expected_factor_count=89,
    ) is True
    assert service._is_symbol_effectiveness_fresh(
        _DummyDb((latest_calc_date.isoformat(), 88), 89),
        exchange="hyperliquid",
        symbol="BTC",
        period="1h",
        latest_calc_date=latest_calc_date,
        expected_factor_count=89,
    ) is False
    assert service._is_symbol_effectiveness_fresh(
        _DummyDb(("2026-03-20", 89), 89),
        exchange="hyperliquid",
        symbol="BTC",
        period="1h",
        latest_calc_date=latest_calc_date,
        expected_factor_count=89,
    ) is False

    assert service._is_symbol_effectiveness_fresh(
        _DummyDb((latest_calc_date.isoformat(), 81), 81),
        exchange="hyperliquid",
        symbol="LINK",
        period="1h",
        latest_calc_date=latest_calc_date,
        expected_factor_count=89,
    ) is True


def test_compute_symbol_skips_when_effectiveness_is_fresh(monkeypatch):
    service = FactorEffectivenessService()
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    klines = [
        {
            "timestamp": int((start + timedelta(hours=idx)).timestamp()),
            "close": 100.0 + idx,
        }
        for idx in range(100)
    ]

    monkeypatch.setattr(
        "services.factor_data_provider.ensure_kline_coverage",
        lambda db, exchange, symbol, period: klines,
    )
    monkeypatch.setattr(
        service,
        "_is_symbol_effectiveness_fresh",
        lambda db, exchange, symbol, period, latest_calc_date, expected_factor_count: True,
    )
    monkeypatch.setattr(
        factor_effectiveness_service_module,
        "calculate_indicators",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("calculate_indicators should not run for fresh symbols")
        ),
    )

    count = service._compute_symbol(
        db=_DummyDb(),
        exchange="hyperliquid",
        symbol="BTC",
        period="1h",
        force=False,
    )

    assert count == 0
    assert service.get_progress()["current_factor"] == "cached"


def test_compute_factor_windowed_normalizes_sqlite_calc_date_strings(monkeypatch):
    service = FactorEffectivenessService()

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return list(self._rows)

    class _DummyDb:
        def __init__(self):
            self.insert_calls = 0

        def execute(self, statement, params=None):
            sql = str(statement)
            if "SELECT forward_period, calc_date, ic_mean" in sql:
                return _Result([("4h", "2026-03-30", 0.15)])
            if "INSERT INTO factor_effectiveness" in sql:
                self.insert_calls += 1
                return _Result([])
            return _Result([])

    monkeypatch.setattr(
        service,
        "_align_series",
        lambda fvals, closes, fp_hours, n_bars: ([1.0] * 12, [1.0] * 12),
    )
    monkeypatch.setattr(
        service,
        "_calc_ic_fast",
        lambda af, ar: {"ic": 0.2, "win_rate": 0.5, "sample_count": len(af)},
    )
    monkeypatch.setattr(service, "_compute_decay_half_life", lambda ic_by_fp, periods: 6)

    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    klines = [
        {"timestamp": int((start + timedelta(hours=idx)).timestamp())}
        for idx in range(744)
    ]
    fvals = [float(idx) for idx in range(744)]
    closes = [100.0 + idx for idx in range(744)]
    db = _DummyDb()

    count = service._compute_factor_windowed(
        db=db,
        exchange="hyperliquid",
        fname="RSI14",
        fcat="momentum",
        symbol="BTC",
        period="1h",
        fvals=fvals,
        closes=closes,
        klines=klines,
        n_bars=len(klines),
        force=False,
    )

    assert count == 4
    assert db.insert_calls == 4
