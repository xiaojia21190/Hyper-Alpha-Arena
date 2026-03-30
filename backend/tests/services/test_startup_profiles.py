import asyncio
import sys
import types

from services import startup as startup_module


def test_initialize_services_factor_profile_starts_only_factor_runtime(monkeypatch):
    started = []

    monkeypatch.setattr(startup_module, "_start_scheduler_services", lambda: started.append("scheduler"))
    monkeypatch.setattr(
        startup_module,
        "_start_hyperliquid_factor_market_services",
        lambda: started.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_start_factor_services", lambda: started.append("factor"))
    monkeypatch.setattr(
        startup_module,
        "_start_program_execution_services",
        lambda: started.append("program"),
    )
    monkeypatch.setattr(startup_module, "_start_binance_services", lambda: started.append("binance"))
    monkeypatch.setattr(startup_module, "_start_bot_services", lambda: started.append("bot"))

    startup_module.initialize_services("factor")

    assert started == ["scheduler", "hyperliquid", "factor", "program"]


def test_initialize_services_api_profile_starts_only_scheduler(monkeypatch):
    started = []

    monkeypatch.setattr(startup_module, "_start_scheduler_services", lambda: started.append("scheduler"))
    monkeypatch.setattr(
        startup_module,
        "_start_hyperliquid_factor_market_services",
        lambda: started.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_start_factor_services", lambda: started.append("factor"))
    monkeypatch.setattr(
        startup_module,
        "_start_program_execution_services",
        lambda: started.append("program"),
    )
    monkeypatch.setattr(startup_module, "_start_binance_services", lambda: started.append("binance"))
    monkeypatch.setattr(startup_module, "_start_bot_services", lambda: started.append("bot"))

    startup_module.initialize_services("api")

    assert started == ["scheduler"]


def test_initialize_services_full_profile_starts_all_groups(monkeypatch):
    started = []

    monkeypatch.setattr(startup_module, "_start_scheduler_services", lambda: started.append("scheduler"))
    monkeypatch.setattr(
        startup_module,
        "_start_hyperliquid_factor_market_services",
        lambda: started.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_start_factor_services", lambda: started.append("factor"))
    monkeypatch.setattr(
        startup_module,
        "_start_program_execution_services",
        lambda: started.append("program"),
    )
    monkeypatch.setattr(startup_module, "_start_binance_services", lambda: started.append("binance"))
    monkeypatch.setattr(startup_module, "_start_bot_services", lambda: started.append("bot"))

    startup_module.initialize_services("full")

    assert started == ["scheduler", "hyperliquid", "factor", "program", "binance", "bot"]


def test_shutdown_services_factor_profile_stops_only_factor_runtime(monkeypatch):
    stopped = []

    monkeypatch.setattr(
        startup_module,
        "_stop_program_execution_services",
        lambda: stopped.append("program"),
    )
    monkeypatch.setattr(
        startup_module,
        "_stop_hyperliquid_factor_market_services",
        lambda: stopped.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_stop_factor_services", lambda: stopped.append("factor"))
    monkeypatch.setattr(startup_module, "_stop_binance_services", lambda: stopped.append("binance"))
    monkeypatch.setattr(startup_module, "_stop_bot_services", lambda: stopped.append("bot"))

    scheduler_calls = []
    fake_scheduler_module = types.SimpleNamespace(
        stop_scheduler=lambda: scheduler_calls.append("scheduler")
    )
    monkeypatch.setitem(sys.modules, "services.scheduler", fake_scheduler_module)

    startup_module.shutdown_services("factor")

    assert stopped == ["program", "hyperliquid", "factor"]
    assert scheduler_calls == ["scheduler"]


def test_shutdown_services_api_profile_stops_only_scheduler(monkeypatch):
    stopped = []

    monkeypatch.setattr(
        startup_module,
        "_stop_program_execution_services",
        lambda: stopped.append("program"),
    )
    monkeypatch.setattr(
        startup_module,
        "_stop_hyperliquid_factor_market_services",
        lambda: stopped.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_stop_factor_services", lambda: stopped.append("factor"))
    monkeypatch.setattr(startup_module, "_stop_binance_services", lambda: stopped.append("binance"))
    monkeypatch.setattr(startup_module, "_stop_bot_services", lambda: stopped.append("bot"))

    scheduler_calls = []
    fake_scheduler_module = types.SimpleNamespace(
        stop_scheduler=lambda: scheduler_calls.append("scheduler")
    )
    monkeypatch.setitem(sys.modules, "services.scheduler", fake_scheduler_module)

    startup_module.shutdown_services("api")

    assert stopped == []
    assert scheduler_calls == ["scheduler"]


def test_shutdown_services_full_profile_stops_all_groups(monkeypatch):
    stopped = []

    monkeypatch.setattr(
        startup_module,
        "_stop_program_execution_services",
        lambda: stopped.append("program"),
    )
    monkeypatch.setattr(
        startup_module,
        "_stop_hyperliquid_factor_market_services",
        lambda: stopped.append("hyperliquid"),
    )
    monkeypatch.setattr(startup_module, "_stop_factor_services", lambda: stopped.append("factor"))
    monkeypatch.setattr(startup_module, "_stop_binance_services", lambda: stopped.append("binance"))
    monkeypatch.setattr(startup_module, "_stop_bot_services", lambda: stopped.append("bot"))

    scheduler_calls = []
    fake_scheduler_module = types.SimpleNamespace(
        stop_scheduler=lambda: scheduler_calls.append("scheduler")
    )
    monkeypatch.setitem(sys.modules, "services.scheduler", fake_scheduler_module)

    startup_module.shutdown_services("full")

    assert stopped == ["bot", "binance", "program", "hyperliquid", "factor"]
    assert scheduler_calls == ["scheduler"]


def test_hyperliquid_factor_market_services_start_market_flow_and_cleanup(monkeypatch):
    calls = []

    monkeypatch.setattr(startup_module, "build_market_stream_symbols", lambda: ["BTC"])
    monkeypatch.setattr(
        startup_module,
        "start_market_stream",
        lambda symbols, interval_seconds=18: calls.append(("market_stream", symbols, interval_seconds)),
    )
    def _capture_create_task(coro):
        calls.append(("create_task", coro))
        coro.close()
        return None

    monkeypatch.setattr(asyncio, "create_task", _capture_create_task)
    monkeypatch.setattr(
        startup_module.task_scheduler,
        "add_interval_task",
        lambda **kwargs: calls.append(("task", kwargs["task_id"])),
    )

    class _DummyQuery:
        @staticmethod
        def first():
            return types.SimpleNamespace(sampling_interval=9)

    class _DummyDb:
        @staticmethod
        def query(_model):
            return _DummyQuery()

    class _DummySession:
        def __enter__(self):
            return _DummyDb()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setitem(
        sys.modules,
        "database.connection",
        types.SimpleNamespace(SessionLocal=lambda: _DummySession()),
    )
    monkeypatch.setitem(
        sys.modules,
        "database.models",
        types.SimpleNamespace(GlobalSamplingConfig=object),
    )

    class _DummyAsyncService:
        async def start(self):
            return None

    monkeypatch.setitem(
        sys.modules,
        "services.hyperliquid_snapshot_service",
        types.SimpleNamespace(hyperliquid_snapshot_service=_DummyAsyncService()),
    )
    monkeypatch.setitem(
        sys.modules,
        "services.kline_realtime_collector",
        types.SimpleNamespace(realtime_collector=_DummyAsyncService()),
    )

    market_flow = types.SimpleNamespace(start=lambda: calls.append(("market_flow", "start")))
    monkeypatch.setitem(
        sys.modules,
        "services.market_flow_collector",
        types.SimpleNamespace(
            market_flow_collector=market_flow,
            cleanup_old_market_flow_data=lambda: None,
        ),
    )

    startup_module._start_hyperliquid_factor_market_services()

    assert ("market_flow", "start") in calls
    assert ("task", "market_flow_data_cleanup") in calls


def test_program_execution_services_wire_price_subscription_and_shutdown(monkeypatch):
    subscribed = []
    unsubscribed = []

    monkeypatch.setattr(startup_module, "subscribe_price_updates", lambda handler: subscribed.append(handler))
    monkeypatch.setattr(
        startup_module,
        "unsubscribe_price_updates",
        lambda handler: unsubscribed.append(handler),
    )

    startup_module._start_program_execution_services()
    startup_module._stop_program_execution_services()

    assert subscribed == [startup_module._program_price_update_handler]
    assert unsubscribed == [startup_module._program_price_update_handler]
