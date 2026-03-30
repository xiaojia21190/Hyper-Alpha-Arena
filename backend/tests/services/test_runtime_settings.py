import importlib

import pytest

import config.settings as settings


@pytest.fixture(autouse=True)
def _restore_settings():
    importlib.reload(settings)
    yield
    importlib.reload(settings)


def _reload_settings(monkeypatch, **env_vars):
    monkeypatch.delenv("APP_RUNTIME_PROFILE", raising=False)
    monkeypatch.delenv("FRONTEND_WATCHER_ENABLED", raising=False)

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return importlib.reload(settings)


def test_runtime_profile_defaults_to_full(monkeypatch):
    settings_module = _reload_settings(monkeypatch)

    assert settings_module.APP_RUNTIME_PROFILE == "full"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is True
    assert settings_module.BOT_RUNTIME_ENABLED is True
    assert settings_module.FRONTEND_WATCHER_ENABLED is False


def test_runtime_profile_api_disables_background_services(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="api")

    assert settings_module.APP_RUNTIME_PROFILE == "api"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is False
    assert settings_module.FACTOR_RUNTIME_ENABLED is False
    assert settings_module.BINANCE_RUNTIME_ENABLED is False
    assert settings_module.BOT_RUNTIME_ENABLED is False


def test_runtime_profile_factor_enables_factor_background_services(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="factor")

    assert settings_module.APP_RUNTIME_PROFILE == "factor"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is False
    assert settings_module.BOT_RUNTIME_ENABLED is False


def test_runtime_profile_full_keeps_optional_services(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="full")

    assert settings_module.APP_RUNTIME_PROFILE == "full"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is True
    assert settings_module.BOT_RUNTIME_ENABLED is True


def test_invalid_runtime_profile_falls_back_to_full(monkeypatch):
    settings_module = _reload_settings(monkeypatch, APP_RUNTIME_PROFILE="unexpected")

    assert settings_module.APP_RUNTIME_PROFILE == "full"
    assert settings_module.BACKGROUND_SERVICES_ENABLED is True
    assert settings_module.FACTOR_RUNTIME_ENABLED is True
    assert settings_module.BINANCE_RUNTIME_ENABLED is True
    assert settings_module.BOT_RUNTIME_ENABLED is True


def test_frontend_watcher_flag_can_be_enabled(monkeypatch):
    settings_module = _reload_settings(monkeypatch, FRONTEND_WATCHER_ENABLED="true")

    assert settings_module.FRONTEND_WATCHER_ENABLED is True
