import sys
import types

import main as main_module


class _Field:
    def __eq__(self, other):
        return ("eq", other)

    def in_(self, values):
        return ("in", tuple(values))


class _FakeResult:
    def __init__(self, rows=None, scalar_value=None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def __iter__(self):
        return iter(self._rows)

    def scalar(self):
        return self._scalar_value


class _StartupQuery:
    def __init__(self, db, model):
        self._db = db
        self._model = model

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._db.first_results.get(self._model)

    def count(self):
        return self._db.count_results.get(self._model, 0)

    def delete(self, synchronize_session=False):
        return self._db.delete_results.get(self._model, 0)


class _StartupDb:
    def __init__(self, first_results, count_results, delete_results):
        self.first_results = first_results
        self.count_results = count_results
        self.delete_results = delete_results

    def execute(self, statement):
        sql = str(statement).lower()
        if "information_schema.columns" in sql and "ai_decision_logs" in sql:
            return _FakeResult(
                rows=[
                    ("prompt_snapshot",),
                    ("reasoning_snapshot",),
                    ("decision_snapshot",),
                    ("hyperliquid_environment",),
                ]
            )
        if "information_schema.columns" in sql and "global_sampling_configs" in sql:
            return _FakeResult(rows=[("sampling_depth",)])
        if "information_schema.columns" in sql and "crypto_klines" in sql:
            return _FakeResult(rows=[("exchange",), ("environment",)])
        if "select count(*) from ai_decision_logs where hyperliquid_environment is null" in sql:
            return _FakeResult(scalar_value=0)
        return _FakeResult(rows=[])

    def query(self, model):
        return _StartupQuery(self, model)

    def add(self, instance):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None

    def refresh(self, instance):
        return None

    def close(self):
        return None


def _install_module(monkeypatch, module_name: str, **attrs):
    module = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, module_name, module)
    return module


def test_on_startup_dispatches_runtime_profile_to_initialize_services(monkeypatch):
    calls = []
    initialize_calls = []

    class _FakeTradingConfig:
        pass

    class _FakeUser:
        username = _Field()

    class _FakeSystemConfig:
        key = _Field()

    class _FakeGlobalSamplingConfig:
        pass

    class _FakeKlineCollectionTask:
        status = _Field()

    class _NoStartThread:
        def __init__(self, target, daemon=True):
            self.target = target
            self.daemon = daemon

        def start(self):
            calls.append("thread_started")

    fake_default_user = object()
    fake_system_config = types.SimpleNamespace(value="testnet")
    fake_global_sampling = types.SimpleNamespace(sampling_depth=5)

    def _session_factory():
        return _StartupDb(
            first_results={
                _FakeUser: fake_default_user,
                _FakeSystemConfig: fake_system_config,
                _FakeGlobalSamplingConfig: fake_global_sampling,
            },
            count_results={_FakeTradingConfig: 1},
            delete_results={_FakeKlineCollectionTask: 0},
        )

    sampling_pool = types.SimpleNamespace(
        default_max_samples=10,
        set_max_samples=lambda symbol, depth: calls.append(("sampling", symbol, depth)),
    )

    _install_module(monkeypatch, "database.migration_manager", run_all_migrations=lambda: calls.append("migrations"))
    _install_module(monkeypatch, "database.schema_validator", validate_and_sync_schema=lambda: calls.append("schema"))
    _install_module(monkeypatch, "services.prompt_initializer", seed_prompt_templates=lambda db: calls.append("seed_prompt"))
    _install_module(monkeypatch, "services.system_logger", setup_system_logger=lambda: calls.append("system_logger"))
    _install_module(monkeypatch, "services.sampling_pool", sampling_pool=sampling_pool)
    _install_module(monkeypatch, "services.trading_commands", AI_TRADING_SYMBOLS=["BTC"])
    _install_module(monkeypatch, "services.hyperliquid_symbol_service", get_selected_symbols=lambda: ["BTC"])
    _install_module(
        monkeypatch,
        "services.startup",
        initialize_services=lambda profile: initialize_calls.append(profile),
    )

    monkeypatch.setattr(main_module, "TradingConfig", _FakeTradingConfig)
    monkeypatch.setattr(main_module, "User", _FakeUser)
    monkeypatch.setattr(main_module, "SystemConfig", _FakeSystemConfig)
    monkeypatch.setattr(
        main_module,
        "SessionLocal",
        _session_factory,
    )
    monkeypatch.setattr(
        main_module,
        "Base",
        types.SimpleNamespace(metadata=types.SimpleNamespace(create_all=lambda bind: calls.append("create_all"))),
    )
    monkeypatch.setattr(main_module, "engine", object())
    monkeypatch.setattr(main_module, "FRONTEND_WATCHER_ENABLED", False)
    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", True)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")
    monkeypatch.setattr(main_module.threading, "Thread", _NoStartThread)

    if "database.models" in sys.modules:
        monkeypatch.setattr(sys.modules["database.models"], "GlobalSamplingConfig", _FakeGlobalSamplingConfig, raising=False)
        monkeypatch.setattr(sys.modules["database.models"], "KlineCollectionTask", _FakeKlineCollectionTask, raising=False)
    else:
        _install_module(
            monkeypatch,
            "database.models",
            GlobalSamplingConfig=_FakeGlobalSamplingConfig,
            KlineCollectionTask=_FakeKlineCollectionTask,
        )

    main_module.on_startup()

    assert initialize_calls == ["factor"]


def test_on_startup_skips_initialize_and_warmup_when_background_disabled(monkeypatch):
    calls = []
    initialize_calls = []

    class _FakeTradingConfig:
        pass

    class _FakeUser:
        username = _Field()

    class _FakeSystemConfig:
        key = _Field()

    class _FakeGlobalSamplingConfig:
        pass

    class _FakeKlineCollectionTask:
        status = _Field()

    class _NoStartThread:
        def __init__(self, target, daemon=True):
            self.target = target
            self.daemon = daemon

        def start(self):
            calls.append("thread_started")

    fake_default_user = object()
    fake_system_config = types.SimpleNamespace(value="testnet")
    fake_global_sampling = types.SimpleNamespace(sampling_depth=5)

    def _session_factory():
        return _StartupDb(
            first_results={
                _FakeUser: fake_default_user,
                _FakeSystemConfig: fake_system_config,
                _FakeGlobalSamplingConfig: fake_global_sampling,
            },
            count_results={_FakeTradingConfig: 1},
            delete_results={_FakeKlineCollectionTask: 0},
        )

    sampling_pool = types.SimpleNamespace(
        default_max_samples=10,
        set_max_samples=lambda symbol, depth: calls.append(("sampling", symbol, depth)),
    )

    _install_module(monkeypatch, "database.migration_manager", run_all_migrations=lambda: calls.append("migrations"))
    _install_module(monkeypatch, "database.schema_validator", validate_and_sync_schema=lambda: calls.append("schema"))
    _install_module(monkeypatch, "services.prompt_initializer", seed_prompt_templates=lambda db: calls.append("seed_prompt"))
    _install_module(monkeypatch, "services.system_logger", setup_system_logger=lambda: calls.append("system_logger"))
    _install_module(monkeypatch, "services.sampling_pool", sampling_pool=sampling_pool)
    _install_module(monkeypatch, "services.trading_commands", AI_TRADING_SYMBOLS=["BTC"])
    _install_module(monkeypatch, "services.hyperliquid_symbol_service", get_selected_symbols=lambda: ["BTC"])
    _install_module(
        monkeypatch,
        "services.startup",
        initialize_services=lambda profile: initialize_calls.append(profile),
    )

    monkeypatch.setattr(main_module, "TradingConfig", _FakeTradingConfig)
    monkeypatch.setattr(main_module, "User", _FakeUser)
    monkeypatch.setattr(main_module, "SystemConfig", _FakeSystemConfig)
    monkeypatch.setattr(main_module, "SessionLocal", _session_factory)
    monkeypatch.setattr(
        main_module,
        "Base",
        types.SimpleNamespace(metadata=types.SimpleNamespace(create_all=lambda bind: calls.append("create_all"))),
    )
    monkeypatch.setattr(main_module, "engine", object())
    monkeypatch.setattr(main_module, "FRONTEND_WATCHER_ENABLED", False)
    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", False)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")
    monkeypatch.setattr(main_module.threading, "Thread", _NoStartThread)

    if "database.models" in sys.modules:
        monkeypatch.setattr(sys.modules["database.models"], "GlobalSamplingConfig", _FakeGlobalSamplingConfig, raising=False)
        monkeypatch.setattr(sys.modules["database.models"], "KlineCollectionTask", _FakeKlineCollectionTask, raising=False)
    else:
        _install_module(
            monkeypatch,
            "database.models",
            GlobalSamplingConfig=_FakeGlobalSamplingConfig,
            KlineCollectionTask=_FakeKlineCollectionTask,
        )

    main_module.on_startup()

    assert initialize_calls == []
    assert "thread_started" not in calls


def test_on_startup_starts_frontend_watcher_when_enabled(monkeypatch):
    calls = []
    thread_calls = []
    initialize_calls = []

    class _FakeTradingConfig:
        pass

    class _FakeUser:
        username = _Field()

    class _FakeSystemConfig:
        key = _Field()

    class _FakeGlobalSamplingConfig:
        pass

    class _FakeKlineCollectionTask:
        status = _Field()

    class _ThreadRecorder:
        def __init__(self, target, daemon=True):
            thread_calls.append(("init", target, daemon))
            self.target = target
            self.daemon = daemon

        def start(self):
            thread_calls.append(("start", self.target, self.daemon))

    fake_default_user = object()
    fake_system_config = types.SimpleNamespace(value="testnet")
    fake_global_sampling = types.SimpleNamespace(sampling_depth=5)

    def _session_factory():
        return _StartupDb(
            first_results={
                _FakeUser: fake_default_user,
                _FakeSystemConfig: fake_system_config,
                _FakeGlobalSamplingConfig: fake_global_sampling,
            },
            count_results={_FakeTradingConfig: 1},
            delete_results={_FakeKlineCollectionTask: 0},
        )

    sampling_pool = types.SimpleNamespace(
        default_max_samples=10,
        set_max_samples=lambda symbol, depth: calls.append(("sampling", symbol, depth)),
    )

    _install_module(monkeypatch, "database.migration_manager", run_all_migrations=lambda: calls.append("migrations"))
    _install_module(monkeypatch, "database.schema_validator", validate_and_sync_schema=lambda: calls.append("schema"))
    _install_module(monkeypatch, "services.prompt_initializer", seed_prompt_templates=lambda db: calls.append("seed_prompt"))
    _install_module(monkeypatch, "services.system_logger", setup_system_logger=lambda: calls.append("system_logger"))
    _install_module(monkeypatch, "services.sampling_pool", sampling_pool=sampling_pool)
    _install_module(monkeypatch, "services.trading_commands", AI_TRADING_SYMBOLS=["BTC"])
    _install_module(monkeypatch, "services.hyperliquid_symbol_service", get_selected_symbols=lambda: ["BTC"])
    _install_module(
        monkeypatch,
        "services.startup",
        initialize_services=lambda profile: initialize_calls.append(profile),
    )

    monkeypatch.setattr(main_module, "TradingConfig", _FakeTradingConfig)
    monkeypatch.setattr(main_module, "User", _FakeUser)
    monkeypatch.setattr(main_module, "SystemConfig", _FakeSystemConfig)
    monkeypatch.setattr(main_module, "SessionLocal", _session_factory)
    monkeypatch.setattr(
        main_module,
        "Base",
        types.SimpleNamespace(metadata=types.SimpleNamespace(create_all=lambda bind: calls.append("create_all"))),
    )
    monkeypatch.setattr(main_module, "engine", object())
    monkeypatch.setattr(main_module, "FRONTEND_WATCHER_ENABLED", True)
    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", False)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")
    monkeypatch.setattr(main_module.threading, "Thread", _ThreadRecorder)

    if "database.models" in sys.modules:
        monkeypatch.setattr(sys.modules["database.models"], "GlobalSamplingConfig", _FakeGlobalSamplingConfig, raising=False)
        monkeypatch.setattr(sys.modules["database.models"], "KlineCollectionTask", _FakeKlineCollectionTask, raising=False)
    else:
        _install_module(
            monkeypatch,
            "database.models",
            GlobalSamplingConfig=_FakeGlobalSamplingConfig,
            KlineCollectionTask=_FakeKlineCollectionTask,
        )

    main_module.on_startup()

    assert initialize_calls == []
    assert thread_calls == [
        ("init", main_module.watch_frontend_files, True),
        ("start", main_module.watch_frontend_files, True),
    ]


def test_on_shutdown_dispatches_runtime_profile(monkeypatch):
    calls = []

    _install_module(monkeypatch, "services.startup", shutdown_services=lambda profile: calls.append(profile))
    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", True)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")

    main_module.on_shutdown()

    assert calls == ["factor"]


def test_on_shutdown_skips_dispatch_when_background_disabled(monkeypatch):
    calls = []

    _install_module(monkeypatch, "services.startup", shutdown_services=lambda profile: calls.append(profile))
    monkeypatch.setattr(main_module, "BACKGROUND_SERVICES_ENABLED", False)
    monkeypatch.setattr(main_module, "APP_RUNTIME_PROFILE", "factor")

    main_module.on_shutdown()

    assert calls == []
