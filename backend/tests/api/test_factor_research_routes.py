from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import factor_research_routes as factor_research_routes_module


def test_factor_research_run_returns_ranked_results(monkeypatch):
    class _DummyAutomationService:
        def trigger_run(self, **kwargs):
            return {
                "status": "started",
                "config": kwargs,
                **kwargs,
            }

    app = FastAPI()
    app.include_router(factor_research_routes_module.router)

    monkeypatch.setattr(
        factor_research_routes_module,
        "factor_research_automation_service",
        _DummyAutomationService(),
        raising=False,
    )

    client = TestClient(app)
    response = client.post("/api/factor-research/run", json={})

    assert response.status_code == 202
    assert response.json()["status"] == "started"
    assert response.json()["config"]["top_n_symbols"] == 20


def test_factor_research_status_returns_scheduler_state(monkeypatch):
    class _DummyAutomationService:
        def get_status(self):
            return {
                "enabled": True,
                "status": "idle",
                "last_run_status": "success",
                "progress": {
                    "phase": "complete",
                    "current": 3,
                    "total": 3,
                    "current_factor": "ATR_RATIO",
                },
                "last_top_factor": {"factor_name": "ATR_RATIO", "score": 2.4},
            }

    app = FastAPI()
    app.include_router(factor_research_routes_module.router)

    monkeypatch.setattr(
        factor_research_routes_module,
        "factor_research_automation_service",
        _DummyAutomationService(),
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/factor-research/status")

    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["progress"]["phase"] == "complete"
    assert response.json()["last_top_factor"]["factor_name"] == "ATR_RATIO"
