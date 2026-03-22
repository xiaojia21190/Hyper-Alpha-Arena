from datetime import datetime, timezone

from database.models import Account, FactorPortfolioCandidate, User
from services.factor_portfolio_deployment_service import FactorPortfolioDeploymentService


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
