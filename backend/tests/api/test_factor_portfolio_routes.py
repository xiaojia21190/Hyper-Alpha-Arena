from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import factor_portfolio_routes as factor_portfolio_routes_module


def test_latest_factor_portfolio_run(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "get_latest_portfolio_run",
        lambda db: {
            "run": {"id": 11, "status": "success"},
            "portfolio_candidates": [{"id": 101, "score": 2.1}],
            "top_portfolio": {"id": 101, "score": 2.1},
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/latest")

    assert response.status_code == 200
    assert response.json()["run"]["id"] == 11
    assert response.json()["top_portfolio"]["id"] == 101


def test_latest_factor_portfolio_run_returns_empty_payload_when_missing(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "get_latest_portfolio_run",
        lambda db: None,
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["run"] is None
    assert body["portfolio_candidates"] == []
    assert body["top_portfolio"] is None


def test_latest_live_gate_status(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "get_latest_live_gate_status",
        lambda db: {
            "latest_run": {"id": 11, "status": "success"},
            "decision_run": {"id": 10, "status": "success"},
            "live_decision": {"decision": "not_ready"},
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/live-gate/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["latest_run"]["id"] == 11
    assert body["decision_run"]["id"] == 10
    assert body["live_decision"]["decision"] == "not_ready"


def test_latest_live_gate_status_returns_empty_payload_when_missing(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "get_latest_live_gate_status",
        lambda db: None,
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/live-gate/latest")

    assert response.status_code == 200
    body = response.json()
    assert body["latest_run"] is None
    assert body["decision_run"] is None
    assert body["live_decision"] is None


def test_deploy_live_requires_confirm(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    def _raise(*args, **kwargs):
        raise ValueError("Live deployment requires confirm_live=true")

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "deploy_portfolio_candidate",
        _raise,
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/api/factor-portfolios/5/deploy-live",
        json={"account_id": 2, "confirm_live": False, "signal_pool_ids": []},
    )

    assert response.status_code == 400
    assert "confirm_live=true" in response.json()["detail"]


def test_deploy_paper_success(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "deploy_portfolio_candidate",
        lambda *args, **kwargs: {
            "deployment": {"id": 1, "mode": "paper", "status": "deployed"},
            "program": {"id": 7},
            "binding": {"id": 9},
            "portfolio": {"id": 5},
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/api/factor-portfolios/5/deploy-paper",
        json={"account_id": 2, "signal_pool_ids": []},
    )

    assert response.status_code == 200
    assert response.json()["deployment"]["mode"] == "paper"


def test_factor_portfolio_run_detail(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "get_portfolio_run_detail",
        lambda db, run_id: {
            "run": {"id": run_id, "status": "success"},
            "portfolio_candidates": [{"id": 301}],
        },
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/runs/21")

    assert response.status_code == 200
    assert response.json()["run"]["id"] == 21


def test_factor_portfolio_deployments_list(monkeypatch):
    app = FastAPI()
    app.include_router(factor_portfolio_routes_module.router)
    app.dependency_overrides[factor_portfolio_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        factor_portfolio_routes_module,
        "list_portfolio_deployments",
        lambda db, account_id=None, limit=50: [
            {"id": 1, "mode": "paper"},
            {"id": 2, "mode": "live"},
        ],
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-portfolios/deployments?account_id=7&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["mode"] == "paper"
