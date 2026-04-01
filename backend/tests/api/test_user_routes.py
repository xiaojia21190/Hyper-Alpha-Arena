from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import user_routes as user_routes_module


class _DummyConfig:
    def __init__(self, selected_exchange: str = "hyperliquid"):
        self.selected_exchange = selected_exchange


class _DummyUser:
    def __init__(self, user_id: int = 1):
        self.id = user_id


def test_get_exchange_config_returns_selected_exchange(monkeypatch):
    app = FastAPI()
    app.include_router(user_routes_module.router)
    app.dependency_overrides[user_routes_module.get_db] = lambda: object()

    monkeypatch.setattr(
        user_routes_module,
        "_get_or_create_default_user",
        lambda db: _DummyUser(1),
        raising=False,
    )
    monkeypatch.setattr(
        user_routes_module,
        "_get_or_create_exchange_config",
        lambda db, user_id: _DummyConfig("binance"),
        raising=False,
    )

    client = TestClient(app)
    response = client.get("/api/users/exchange-config")

    assert response.status_code == 200
    assert response.json()["selected_exchange"] == "binance"


def test_update_exchange_config_persists_and_returns_value(monkeypatch):
    app = FastAPI()
    app.include_router(user_routes_module.router)

    class _DummyDb:
        def commit(self):
            return None

        def refresh(self, row):
            return None

        def rollback(self):
            return None

    app.dependency_overrides[user_routes_module.get_db] = lambda: _DummyDb()

    config = _DummyConfig("hyperliquid")

    monkeypatch.setattr(
        user_routes_module,
        "_get_or_create_default_user",
        lambda db: _DummyUser(1),
        raising=False,
    )
    monkeypatch.setattr(
        user_routes_module,
        "_get_or_create_exchange_config",
        lambda db, user_id: config,
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/api/users/exchange-config",
        json={"selected_exchange": "aster"},
    )

    assert response.status_code == 200
    assert response.json()["selected_exchange"] == "aster"
    assert config.selected_exchange == "aster"
