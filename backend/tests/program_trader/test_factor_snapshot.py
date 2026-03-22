from program_trader.data_provider import compute_factor_snapshot
from services import factor_effectiveness_service as factor_effectiveness_service_module
from services import factor_registry as factor_registry_module
from services import technical_indicators as technical_indicators_module


class _DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _DummyExecuteResult:
    def fetchone(self):
        return None


class _DummyDb:
    def query(self, model):
        return _DummyQuery()

    def execute(self, *args, **kwargs):
        return _DummyExecuteResult()


def test_compute_factor_snapshot_supports_builtin_registry_factor(monkeypatch):
    monkeypatch.setattr(
        factor_registry_module,
        "FACTOR_REGISTRY",
        [
            {
                "name": "RSI14",
                "category": "momentum",
                "compute_type": "technical",
                "indicator_key": "RSI14",
            }
        ],
    )
    monkeypatch.setattr(
        technical_indicators_module,
        "calculate_indicators",
        lambda klines, indicators: {"RSI14": [10.0, 20.0, 30.0]},
    )
    monkeypatch.setattr(
        factor_effectiveness_service_module.FactorEffectivenessService,
        "_extract_full_series",
        lambda self, *args, **kwargs: [10.0, 20.0, 30.0],
    )

    result = compute_factor_snapshot(
        db=_DummyDb(),
        symbol="BTC",
        factor_name="RSI14",
        period="1h",
        exchange="hyperliquid",
        klines_loader=lambda period, count: [
            {
                "timestamp": index,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": 1.0,
                "volume": 1.0,
            }
            for index in range(60)
        ],
        include_effectiveness=False,
    )

    assert result["value"] == 30.0
    assert result["category"] == "momentum"
