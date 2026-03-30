from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services import program_execution_service as program_execution_service_module
from services.program_execution_service import ProgramExecutionService


def _new_service():
    ProgramExecutionService._instance = None
    return ProgramExecutionService()


class _FakeBindingQuery:
    def __init__(self, row, first_result):
        self._row = row
        self._first_result = first_result
        self.filters = []

    def filter(self, *args, **kwargs):
        self.filters.extend(args)
        return self

    def first(self):
        if self._first_result is None:
            return None
        return self._row


class _FakeDb:
    def __init__(self, binding, first_result=True):
        self._binding = binding
        self._first_result = first_result
        self.commit_calls = 0
        self.last_query = None

    def query(self, _model):
        self.last_query = _FakeBindingQuery(self._binding, self._first_result)
        return self.last_query

    def commit(self):
        self.commit_calls += 1
        return None

    def close(self):
        return None


def test_on_price_update_triggers_scheduled_binding_execution(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    executed: list[tuple[int, str, datetime]] = []

    service._binding_states = {
        101: {
            "binding_id": 101,
            "account_id": 7,
            "program_id": 9,
            "trigger_interval": 60,
            "last_trigger_at": event_time - timedelta(seconds=120),
            "signal_pool_ids": [],
        }
    }
    monkeypatch.setattr(service, "_maybe_refresh_cache", lambda: None)
    monkeypatch.setattr(
        service,
        "_execute_scheduled_trigger",
        lambda binding_id, symbol, ts: executed.append((binding_id, symbol, ts)),
    )

    service.on_price_update("BTC", 100000.0, event_time)

    assert executed == [(101, "", event_time)]


def test_on_price_update_skips_binding_when_interval_not_elapsed(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    executed: list[int] = []

    service._binding_states = {
        101: {
            "binding_id": 101,
            "account_id": 7,
            "program_id": 9,
            "trigger_interval": 300,
            "last_trigger_at": event_time - timedelta(seconds=120),
            "signal_pool_ids": [],
        }
    }
    monkeypatch.setattr(service, "_maybe_refresh_cache", lambda: None)
    monkeypatch.setattr(
        service,
        "_execute_scheduled_trigger",
        lambda binding_id, symbol, ts: executed.append(binding_id),
    )

    service.on_price_update("BTC", 100000.0, event_time)

    assert executed == []


def test_execute_scheduled_trigger_calls_execute_binding_with_scheduled_context(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    binding = SimpleNamespace(id=101, is_active=True, is_deleted=False)
    calls: list[dict] = []

    fake_db = _FakeDb(binding)
    monkeypatch.setattr(program_execution_service_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        service,
        "_execute_binding",
        lambda db, target_binding, symbol, pool, market_data_snapshot, triggered_signals, trigger_type, event_time: calls.append(
            {
                "binding": target_binding,
                "symbol": symbol,
                "pool": pool,
                "snapshot": market_data_snapshot,
                "signals": triggered_signals,
                "trigger_type": trigger_type,
                "event_time": event_time,
            }
        ),
    )

    service._execute_scheduled_trigger(101, "", event_time)

    assert len(calls) == 1
    assert calls[0]["binding"] is binding
    assert calls[0]["symbol"] == ""
    assert calls[0]["pool"] == {"pool_id": None, "pool_name": None}
    assert calls[0]["snapshot"] == {}
    assert calls[0]["signals"] == []
    assert calls[0]["trigger_type"] == "scheduled"
    assert calls[0]["event_time"] == event_time
    assert fake_db.last_query is not None
    assert len(fake_db.last_query.filters) == 3
    assert any(".id" in str(expr) for expr in fake_db.last_query.filters)
    assert any("is_active" in str(expr) for expr in fake_db.last_query.filters)
    assert any("is_deleted" in str(expr) for expr in fake_db.last_query.filters)


def test_execute_scheduled_trigger_refreshes_last_trigger_at(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    old_time = event_time - timedelta(seconds=3600)
    binding = SimpleNamespace(
        id=101,
        is_active=True,
        is_deleted=False,
        account_id=7,
        program_id=9,
        last_trigger_at=old_time,
        signal_pool_ids=None,
        params_override=None,
        exchange="hyperliquid",
        program=SimpleNamespace(name="scheduled-program", code="pass", params=None),
        account=SimpleNamespace(id=7, name="paper"),
    )
    fake_db = _FakeDb(binding)
    service._binding_states = {
        101: {
            "binding_id": 101,
            "account_id": 7,
            "program_id": 9,
            "trigger_interval": 60,
            "last_trigger_at": old_time,
            "signal_pool_ids": [],
        }
    }

    monkeypatch.setattr(program_execution_service_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(service, "_get_wallet_address", lambda db, account, exchange: "0xabc")
    monkeypatch.setattr(
        "services.hyperliquid_environment.get_global_trading_mode",
        lambda db: "testnet",
    )
    monkeypatch.setattr(
        "services.hyperliquid_environment.get_hyperliquid_client",
        lambda db, account_id, override_environment=None: None,
    )
    monkeypatch.setattr(
        "services.hyperliquid_environment.get_leverage_settings",
        lambda db, account_id, environment: {"max_leverage": 5, "default_leverage": 2},
    )
    monkeypatch.setattr(program_execution_service_module, "DataProvider", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(service, "_build_market_data", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(
        program_execution_service_module,
        "execute_strategy",
        lambda code, market_data, params: SimpleNamespace(
            success=True,
            decision=SimpleNamespace(
                operation="hold",
                symbol="BTC",
                reason="scheduled-check",
                leverage=1,
                target_portion_of_balance=0.0,
            ),
        ),
    )
    monkeypatch.setattr(service, "_log_execution", lambda *args, **kwargs: 1)
    monkeypatch.setattr(service, "_handle_decision", lambda *args, **kwargs: None)

    service._execute_scheduled_trigger(101, "", event_time)

    assert fake_db.commit_calls >= 1
    assert binding.last_trigger_at == event_time
    assert service._binding_states[101]["last_trigger_at"] == event_time


def test_execute_scheduled_trigger_skips_inactive_binding(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    called = []

    inactive_binding = SimpleNamespace(id=101, is_active=False, is_deleted=False)
    fake_db = _FakeDb(inactive_binding, first_result=None)
    monkeypatch.setattr(program_execution_service_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        service,
        "_execute_binding",
        lambda *args, **kwargs: called.append("executed"),
    )

    service._execute_scheduled_trigger(101, "", event_time)

    assert called == []
    assert fake_db.last_query is not None
    assert len(fake_db.last_query.filters) == 3


def test_execute_scheduled_trigger_skips_deleted_binding(monkeypatch):
    service = _new_service()
    event_time = datetime(2026, 3, 27, 12, 0, tzinfo=timezone.utc)
    called = []

    deleted_binding = SimpleNamespace(id=101, is_active=True, is_deleted=True)
    fake_db = _FakeDb(deleted_binding, first_result=None)
    monkeypatch.setattr(program_execution_service_module, "SessionLocal", lambda: fake_db)
    monkeypatch.setattr(
        service,
        "_execute_binding",
        lambda *args, **kwargs: called.append("executed"),
    )

    service._execute_scheduled_trigger(101, "", event_time)

    assert called == []
    assert fake_db.last_query is not None
    assert len(fake_db.last_query.filters) == 3
