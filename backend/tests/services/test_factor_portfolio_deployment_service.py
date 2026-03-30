from datetime import datetime, timezone
import json

from database.models import (
    Account,
    AccountAssetSnapshot,
    AccountProgramBinding,
    FactorPortfolioCandidate,
    FactorPortfolioDeployment,
    FactorResearchRun,
    ProgramExecutionLog,
    User,
)
import services.factor_portfolio_deployment_service as deployment_module
from services.factor_portfolio_deployment_service import (
    FactorPortfolioDeploymentService,
    get_latest_live_gate_status,
)


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeDb:
    def __init__(self, account, candidate, user):
        self._rows = {
            Account: [account],
            FactorPortfolioCandidate: [candidate],
            User: [user],
        }
        self._next_id = 1000

    def query(self, model):
        return _FakeQuery(self._rows.get(model, []))

    def add(self, row):
        if getattr(row, "id", None) is None:
            row.id = self._next_id
            self._next_id += 1
        self._rows.setdefault(type(row), []).append(row)

    def commit(self):
        return None

    def refresh(self, row):
        return None


def test_deploy_live_requires_confirmation():
    service = FactorPortfolioDeploymentService(db=object())
    try:
        service.deploy_portfolio(
            portfolio_id=1,
            account_id=1,
            mode="live",
            confirm_live=False,
        )
    except ValueError as exc:
        assert "confirm_live=true" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unconfirmed live deployment")


def test_deploy_portfolio_creates_program_binding_and_record():
    account = Account(id=7, user_id=2, name="paper")
    candidate = FactorPortfolioCandidate(
        id=9,
        run_id=3,
        name="score_weighted_top_n",
        construction_method="score_weighted_top_n",
        score=2.2,
        components_json='[{"factor_name":"RSI14","category":"momentum","weight":0.6},{"factor_name":"ATR_RATIO","category":"volatility","weight":0.4}]',
    )
    user = User(id=2, username="default")
    db = _FakeDb(account=account, candidate=candidate, user=user)

    payload = FactorPortfolioDeploymentService(db).deploy_portfolio(
        portfolio_id=9,
        account_id=7,
        mode="paper",
        trigger_interval=120,
    )

    assert payload["program"]["id"] > 0
    assert payload["binding"]["id"] > 0
    assert payload["deployment"]["mode"] == "paper"
    assert payload["deployment"]["status"] == "deployed"
    assert payload["portfolio"]["id"] == 9

    bindings = db._rows.get(AccountProgramBinding, [])
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.id == payload["binding"]["id"]
    assert binding.account_id == 7
    assert binding.exchange == "hyperliquid"
    assert binding.scheduled_trigger_enabled is True
    assert binding.trigger_interval == 120


def test_deploy_portfolio_enforces_min_trigger_interval_30_seconds():
    account = Account(id=7, user_id=2, name="paper")
    candidate = FactorPortfolioCandidate(
        id=9,
        run_id=3,
        name="score_weighted_top_n",
        construction_method="score_weighted_top_n",
        score=2.2,
        components_json='[{"factor_name":"RSI14","category":"momentum","weight":0.6},{"factor_name":"ATR_RATIO","category":"volatility","weight":0.4}]',
    )
    user = User(id=2, username="default")
    db = _FakeDb(account=account, candidate=candidate, user=user)

    payload = FactorPortfolioDeploymentService(db).deploy_portfolio(
        portfolio_id=9,
        account_id=7,
        mode="paper",
        trigger_interval=1,
    )

    bindings = db._rows.get(AccountProgramBinding, [])
    assert len(bindings) == 1
    assert bindings[0].trigger_interval == 30
    assert payload["deployment"]["deployment_config"]["trigger_interval"] == 30


class _GateSourceQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, _FilterExpression):
                self.rows = [
                    row for row in self.rows if arg.matches(row)
                ]
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _GateSourceDb:
    def __init__(self, rows_by_model):
        self.rows_by_model = rows_by_model
        self.queried_models = []

    def query(self, model):
        self.queried_models.append(model)
        return _GateSourceQuery(self.rows_by_model.get(model, []))


class _DummyColumn:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return _FilterExpression(self.name, "eq", other)

    def __ge__(self, other):
        return _FilterExpression(self.name, "ge", other)

    def asc(self):
        return self


class _FakeHyperliquidAccountSnapshot:
    account_id = _DummyColumn("account_id")
    environment = _DummyColumn("environment")
    created_at = _DummyColumn("created_at")
    id = _DummyColumn("id")


class _FilterExpression:
    def __init__(self, field_name, operator, value):
        self.field_name = field_name
        self.operator = operator
        self.value = value

    def matches(self, row):
        row_value = getattr(row, self.field_name)
        if self.operator == "eq":
            return row_value == self.value
        if self.operator == "ge":
            return row_value >= self.value
        return True


def test_resolve_paper_gate_context_uses_hyperliquid_snapshot_source_with_environment_and_cutoff(monkeypatch):
    observation_start = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
    account = Account(id=7, user_id=2, name="paper", hyperliquid_environment="testnet")
    paper_deployment = FactorPortfolioDeployment(
        id=201,
        run_id=3,
        portfolio_id=9,
        account_id=7,
        mode="paper",
        status="deployed",
        program_id=101,
        binding_id=301,
        created_at=observation_start,
    )
    execution_logs = [
        ProgramExecutionLog(
            id=401,
            account_id=7,
            program_id=101,
            binding_id=301,
            trigger_type="scheduled",
            success=True,
            decision_action="buy",
            realized_pnl=12.0,
            created_at=datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
        ),
        ProgramExecutionLog(
            id=402,
            account_id=7,
            program_id=101,
            binding_id=301,
            trigger_type="scheduled",
            success=True,
            decision_action="sell",
            realized_pnl=-5.0,
            created_at=datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
        ),
    ]
    # Legacy main-db snapshots show deep drawdown and should be ignored by gate.
    legacy_asset_snapshots = [
        AccountAssetSnapshot(
            id=501,
            account_id=7,
            total_assets=100.0,
            cash=100.0,
            positions_value=0.0,
            event_time=datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
        ),
        AccountAssetSnapshot(
            id=502,
            account_id=7,
            total_assets=20.0,
            cash=20.0,
            positions_value=0.0,
            event_time=datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
        ),
    ]
    main_db = _GateSourceDb(
        {
            Account: [account],
            FactorPortfolioDeployment: [paper_deployment],
            ProgramExecutionLog: execution_logs,
            AccountAssetSnapshot: legacy_asset_snapshots,
        }
    )

    hyperliquid_snapshots = [
        type(
            "_SnapshotRow",
            (),
            {
                "id": 601,
                "account_id": 7,
                "environment": "testnet",
                "created_at": datetime(2026, 3, 24, 9, 30, tzinfo=timezone.utc),
                "total_equity": 300.0,
            },
        )(),
        type(
            "_SnapshotRow",
            (),
            {
                "id": 602,
                "account_id": 7,
                "environment": "mainnet",
                "created_at": datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
                "total_equity": 10.0,
            },
        )(),
        type(
            "_SnapshotRow",
            (),
            {
                "id": 603,
                "account_id": 7,
                "environment": "testnet",
                "created_at": datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
                "total_equity": 100.0,
            },
        )(),
        type(
            "_SnapshotRow",
            (),
            {
                "id": 604,
                "account_id": 7,
                "environment": "testnet",
                "created_at": datetime(2026, 3, 24, 12, 0, tzinfo=timezone.utc),
                "total_equity": 50.0,
            },
        )(),
    ]
    snapshot_db = _GateSourceDb({_FakeHyperliquidAccountSnapshot: hyperliquid_snapshots})
    snapshot_db.closed = False

    def _close_snapshot_db():
        snapshot_db.closed = True

    snapshot_db.close = _close_snapshot_db
    monkeypatch.setattr(
        deployment_module,
        "_get_snapshot_session_and_model",
        lambda: (lambda: snapshot_db, _FakeHyperliquidAccountSnapshot),
    )

    context = FactorPortfolioDeploymentService(main_db)._resolve_paper_gate_context(
        portfolio_id=9,
        paper_account_id=7,
    )

    assert context is not None
    assert context["trade_count"] == 2
    assert context["net_pnl"] == 7.0
    assert context["max_drawdown_percent"] == 50.0
    assert _FakeHyperliquidAccountSnapshot in snapshot_db.queried_models
    assert AccountAssetSnapshot not in main_db.queried_models
    assert snapshot_db.closed is True


def test_auto_decide_live_promotion_returns_not_ready_when_gate_fails(monkeypatch):
    service = FactorPortfolioDeploymentService(db=object())

    monkeypatch.setattr(
        service,
        "_resolve_paper_gate_context",
        lambda **kwargs: {
            "paper_deployment": type(
                "_Deployment",
                (),
                {
                    "id": 11,
                    "run_id": 3,
                    "portfolio_id": 9,
                    "account_id": 7,
                    "mode": "paper",
                    "status": "deployed",
                    "program_id": 101,
                    "binding_id": 201,
                    "deployment_config": None,
                    "deployment_result": None,
                    "error_message": None,
                    "created_at": datetime(2026, 3, 22, tzinfo=timezone.utc),
                    "updated_at": None,
                },
            )(),
            "observation_hours": 2.0,
            "trade_count": 3,
            "winning_trades": 1,
            "win_rate_percent": 33.3,
            "net_pnl": -12.5,
            "max_drawdown_percent": 30.0,
        },
    )

    result = service.auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
        min_observation_hours=24.0,
        min_trades=10,
        min_net_pnl=0.0,
        min_win_rate=50.0,
        max_drawdown_percent_limit=20.0,
    )

    assert result["decision"] == "not_ready"
    assert result["reason"] == "gate_not_passed"
    assert result["gate"]["passed"] is False
    assert set(result["gate"]["failed_checks"]) == {
        "observation_hours",
        "trade_count",
        "net_pnl",
        "win_rate_percent",
        "max_drawdown_percent",
    }
    assert result["live_deployment"] is None


def test_auto_decide_live_promotion_returns_error_when_paper_context_unavailable(monkeypatch):
    service = FactorPortfolioDeploymentService(db=object())

    def _raise_snapshot_failure(**kwargs):
        raise RuntimeError("snapshot_context_unavailable")

    monkeypatch.setattr(service, "_resolve_paper_gate_context", _raise_snapshot_failure)

    result = service.auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
    )

    assert result["decision"] == "error"
    assert result["reason"] == "paper_context_unavailable"
    assert "snapshot_context_unavailable" in result["error"]
    assert result["gate"] is None
    assert result["paper_context"] is None
    assert result["live_deployment"] is None


def test_auto_decide_live_promotion_fail_closed_when_account_environment_missing(monkeypatch):
    observation_start = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
    account = Account(id=7, user_id=2, name="paper", hyperliquid_environment=None)
    paper_deployment = FactorPortfolioDeployment(
        id=211,
        run_id=3,
        portfolio_id=9,
        account_id=7,
        mode="paper",
        status="deployed",
        program_id=101,
        binding_id=301,
        created_at=observation_start,
    )
    execution_logs = [
        ProgramExecutionLog(
            id=411,
            account_id=7,
            program_id=101,
            binding_id=301,
            trigger_type="scheduled",
            success=True,
            decision_action="buy",
            realized_pnl=8.0,
            created_at=datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
        ),
    ]
    main_db = _GateSourceDb(
        {
            Account: [account],
            FactorPortfolioDeployment: [paper_deployment],
            ProgramExecutionLog: execution_logs,
        }
    )

    # Mixed environments exist in snapshot store, but missing account env must fail-closed.
    hyperliquid_snapshots = [
        type(
            "_SnapshotRow",
            (),
            {
                "id": 611,
                "account_id": 7,
                "environment": "testnet",
                "created_at": datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
                "total_equity": 100.0,
            },
        )(),
        type(
            "_SnapshotRow",
            (),
            {
                "id": 612,
                "account_id": 7,
                "environment": "mainnet",
                "created_at": datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
                "total_equity": 20.0,
            },
        )(),
    ]
    snapshot_db = _GateSourceDb({_FakeHyperliquidAccountSnapshot: hyperliquid_snapshots})
    snapshot_db.close = lambda: None
    monkeypatch.setattr(
        deployment_module,
        "_get_snapshot_session_and_model",
        lambda: (lambda: snapshot_db, _FakeHyperliquidAccountSnapshot),
    )

    result = FactorPortfolioDeploymentService(main_db).auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
        min_observation_hours=0.0,
        min_trades=0,
        min_net_pnl=-999.0,
        min_win_rate=0.0,
        max_drawdown_percent_limit=100.0,
    )

    assert result["decision"] == "error"
    assert result["reason"] == "paper_context_unavailable"
    assert "snapshot_context_unavailable" in result["error"]
    assert result["gate"] is None
    assert result["paper_context"] is None
    assert result["live_deployment"] is None


def test_auto_decide_live_promotion_fail_closed_when_account_environment_invalid(monkeypatch):
    observation_start = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
    account = Account(id=7, user_id=2, name="paper", hyperliquid_environment="staging")
    paper_deployment = FactorPortfolioDeployment(
        id=212,
        run_id=3,
        portfolio_id=9,
        account_id=7,
        mode="paper",
        status="deployed",
        program_id=101,
        binding_id=301,
        created_at=observation_start,
    )
    execution_logs = [
        ProgramExecutionLog(
            id=412,
            account_id=7,
            program_id=101,
            binding_id=301,
            trigger_type="scheduled",
            success=True,
            decision_action="buy",
            realized_pnl=8.0,
            created_at=datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
        ),
    ]
    main_db = _GateSourceDb(
        {
            Account: [account],
            FactorPortfolioDeployment: [paper_deployment],
            ProgramExecutionLog: execution_logs,
        }
    )

    snapshot_db_created_count = {"value": 0}

    def _snapshot_factory():
        snapshot_db_created_count["value"] += 1
        return _GateSourceDb({_FakeHyperliquidAccountSnapshot: []})

    monkeypatch.setattr(
        deployment_module,
        "_get_snapshot_session_and_model",
        lambda: (_snapshot_factory, _FakeHyperliquidAccountSnapshot),
    )

    result = FactorPortfolioDeploymentService(main_db).auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
    )

    assert result["decision"] == "error"
    assert result["reason"] == "paper_context_unavailable"
    assert "snapshot_context_unavailable" in result["error"]
    assert result["gate"] is None
    assert result["paper_context"] is None
    assert result["live_deployment"] is None
    assert snapshot_db_created_count["value"] == 0


def test_auto_decide_live_promotion_handles_snapshot_query_failure_and_closes_db(monkeypatch):
    observation_start = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
    account = Account(id=7, user_id=2, name="paper", hyperliquid_environment="testnet")
    paper_deployment = FactorPortfolioDeployment(
        id=213,
        run_id=3,
        portfolio_id=9,
        account_id=7,
        mode="paper",
        status="deployed",
        program_id=101,
        binding_id=301,
        created_at=observation_start,
    )
    execution_logs = [
        ProgramExecutionLog(
            id=413,
            account_id=7,
            program_id=101,
            binding_id=301,
            trigger_type="scheduled",
            success=True,
            decision_action="buy",
            realized_pnl=8.0,
            created_at=datetime(2026, 3, 24, 11, 0, tzinfo=timezone.utc),
        ),
    ]
    main_db = _GateSourceDb(
        {
            Account: [account],
            FactorPortfolioDeployment: [paper_deployment],
            ProgramExecutionLog: execution_logs,
        }
    )

    class _RaisingSnapshotDb:
        def __init__(self):
            self.closed = False

        def query(self, model):
            raise RuntimeError("snapshot_query_failed")

        def close(self):
            self.closed = True

    snapshot_db = _RaisingSnapshotDb()
    monkeypatch.setattr(
        deployment_module,
        "_get_snapshot_session_and_model",
        lambda: (lambda: snapshot_db, _FakeHyperliquidAccountSnapshot),
    )

    result = FactorPortfolioDeploymentService(main_db).auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
    )

    assert result["decision"] == "error"
    assert result["reason"] == "paper_context_unavailable"
    assert "snapshot_context_unavailable" in result["error"]
    assert result["gate"] is None
    assert result["paper_context"] is None
    assert result["live_deployment"] is None
    assert snapshot_db.closed is True


def test_auto_decide_live_promotion_deploys_live_when_gate_passes(monkeypatch):
    service = FactorPortfolioDeploymentService(db=object())

    monkeypatch.setattr(
        service,
        "_resolve_paper_gate_context",
        lambda **kwargs: {
            "paper_deployment": type(
                "_Deployment",
                (),
                {
                    "id": 12,
                    "run_id": 3,
                    "portfolio_id": 9,
                    "account_id": 7,
                    "mode": "paper",
                    "status": "deployed",
                    "program_id": 101,
                    "binding_id": 201,
                    "deployment_config": None,
                    "deployment_result": None,
                    "error_message": None,
                    "created_at": datetime(2026, 3, 20, tzinfo=timezone.utc),
                    "updated_at": None,
                },
            )(),
            "observation_hours": 72.0,
            "trade_count": 30,
            "winning_trades": 18,
            "win_rate_percent": 60.0,
            "net_pnl": 250.0,
            "max_drawdown_percent": 8.5,
        },
    )
    monkeypatch.setattr(service, "_find_existing_live_deployment", lambda **kwargs: None)

    calls: dict = {}

    def _fake_deploy_portfolio(**kwargs):
        calls.update(kwargs)
        return {
            "deployment": {"id": 99, "mode": "live", "status": "deployed"},
            "program": {"id": 1001},
            "binding": {"id": 1002},
            "portfolio": {"id": kwargs["portfolio_id"]},
        }

    monkeypatch.setattr(service, "deploy_portfolio", _fake_deploy_portfolio)

    result = service.auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
        min_observation_hours=24.0,
        min_trades=10,
        min_net_pnl=0.0,
        min_win_rate=50.0,
        max_drawdown_percent_limit=20.0,
        require_live_confirm=True,
    )

    assert result["decision"] == "promoted"
    assert result["gate"]["passed"] is True
    assert result["live_deployment"]["deployment"]["mode"] == "live"
    assert calls["mode"] == "live"
    assert calls["confirm_live"] is True
    assert calls["account_id"] == 8


def test_auto_decide_live_promotion_skips_when_existing_live_found(monkeypatch):
    service = FactorPortfolioDeploymentService(db=object())

    monkeypatch.setattr(
        service,
        "_resolve_paper_gate_context",
        lambda **kwargs: {
            "paper_deployment": type(
                "_Deployment",
                (),
                {
                    "id": 13,
                    "run_id": 3,
                    "portfolio_id": 9,
                    "account_id": 7,
                    "mode": "paper",
                    "status": "deployed",
                    "program_id": 101,
                    "binding_id": 201,
                    "deployment_config": None,
                    "deployment_result": None,
                    "error_message": None,
                    "created_at": datetime(2026, 3, 18, tzinfo=timezone.utc),
                    "updated_at": None,
                },
            )(),
            "observation_hours": 72.0,
            "trade_count": 30,
            "winning_trades": 18,
            "win_rate_percent": 60.0,
            "net_pnl": 250.0,
            "max_drawdown_percent": 8.5,
        },
    )
    monkeypatch.setattr(
        service,
        "_find_existing_live_deployment",
        lambda **kwargs: type(
            "_LiveDeployment",
            (),
            {
                "id": 21,
                "run_id": 3,
                "portfolio_id": 9,
                "account_id": 8,
                "mode": "live",
                "status": "deployed",
                "program_id": 333,
                "binding_id": 444,
                "deployment_config": None,
                "deployment_result": None,
                "error_message": None,
                "created_at": datetime(2026, 3, 22, tzinfo=timezone.utc),
                "updated_at": None,
            },
        )(),
    )
    monkeypatch.setattr(
        service,
        "deploy_portfolio",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("deploy_portfolio should not be called")),
    )

    result = service.auto_decide_live_promotion(
        portfolio_id=9,
        paper_account_id=7,
        live_account_id=8,
    )

    assert result["decision"] == "skipped"
    assert result["reason"] == "already_live_for_target_account"
    assert result["live_deployment"]["already_exists"] is True


class _LiveGateQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _LiveGateDb:
    def __init__(self, runs):
        self.runs = runs

    def query(self, model):
        assert model is FactorResearchRun
        return _LiveGateQuery(self.runs)


def test_get_latest_live_gate_status_prefers_newest_decision_run():
    latest_run = FactorResearchRun(
        id=3,
        exchange="hyperliquid",
        top_n_symbols=20,
        lookback_days=180,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
        period="1h",
        prescreen_limit=10,
        status="success",
        result_json=json.dumps({"top_factor": {"factor_name": "RSI14"}}),
        top_factor_json="{}",
        top_portfolio_json="{}",
        created_at=datetime(2026, 3, 24, tzinfo=timezone.utc),
    )
    decision_run = FactorResearchRun(
        id=2,
        exchange="hyperliquid",
        top_n_symbols=20,
        lookback_days=180,
        objective="return_over_drawdown",
        factor_scope="builtin_only",
        period="1h",
        prescreen_limit=10,
        status="success",
        result_json=json.dumps({
            "auto_live_decision": {
                "decision": "not_ready",
                "reason": "gate_not_passed",
            }
        }),
        top_factor_json="{}",
        top_portfolio_json="{}",
        created_at=datetime(2026, 3, 23, tzinfo=timezone.utc),
    )

    payload = get_latest_live_gate_status(_LiveGateDb([latest_run, decision_run]))

    assert payload is not None
    assert payload["latest_run"]["id"] == 3
    assert payload["decision_run"]["id"] == 2
    assert payload["live_decision"]["decision"] == "not_ready"


def test_get_latest_live_gate_status_returns_none_without_runs():
    payload = get_latest_live_gate_status(_LiveGateDb([]))
    assert payload is None
