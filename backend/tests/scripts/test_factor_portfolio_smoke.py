from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_smoke_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "factor_portfolio_smoke.py"
    spec = importlib.util.spec_from_file_location("factor_portfolio_smoke", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_main_reports_stage_sections(monkeypatch, capsys):
    smoke = _load_smoke_module()

    responses = {
        "/api/factor-research/status": (
            200,
            {
                "status": "idle",
                "last_run_status": "success",
                "last_run_completed_at": "2026-03-30T00:00:00Z",
                "last_top_portfolio": {"portfolio_id": 101},
            },
        ),
        "/api/factor-portfolios/latest": (
            200,
            {
                "run": {"id": 77, "status": "success"},
                "top_portfolio": {"portfolio_id": 101, "name": "score_weighted_top_n"},
            },
        ),
        "/api/factor-portfolios/runs/77": (
            200,
            {"portfolio_candidates": [{"id": 101}, {"id": 102}]},
        ),
        "/api/factor-portfolios/deployments?limit=5": (
            200,
            {
                "items": [
                    {"id": 1, "mode": "paper", "status": "deployed"},
                    {"id": 2, "mode": "live", "status": "stopped"},
                ]
            },
        ),
        "/api/factor-portfolios/live-gate/latest": (
            200,
            {
                "latest_run": {"id": 77, "status": "success"},
                "decision_run": {"id": 76, "status": "success"},
                "live_decision": {"decision": "not_ready", "reason": "gate_not_passed"},
            },
        ),
    }

    monkeypatch.setattr(
        smoke,
        "_get",
        lambda _base_url, path: responses[path],
    )
    monkeypatch.setattr(smoke.sys, "argv", ["factor_portfolio_smoke.py"])

    assert smoke.main() == 0

    output = capsys.readouterr().out
    assert "[stage] research status" in output
    assert "last_run_status=success" in output
    assert "[stage] latest portfolio" in output
    assert "portfolio_id=101" in output
    assert "[stage] deployment summary" in output
    assert "total=2" in output
    assert "paper=1" in output
    assert "live=1" in output
    assert "[stage] live-gate decision" in output
    assert "decision=not_ready" in output


def test_main_warns_when_live_gate_fetch_is_not_200(monkeypatch, capsys):
    smoke = _load_smoke_module()

    responses = {
        "/api/factor-research/status": (
            200,
            {
                "status": "idle",
                "last_run_status": "success",
            },
        ),
        "/api/factor-portfolios/latest": (
            200,
            {
                "run": {"id": 77, "status": "success"},
                "top_portfolio": {"portfolio_id": 101, "name": "score_weighted_top_n"},
            },
        ),
        "/api/factor-portfolios/runs/77": (
            200,
            {"portfolio_candidates": [{"id": 101}]},
        ),
        "/api/factor-portfolios/deployments?limit=5": (
            200,
            {"items": []},
        ),
        "/api/factor-portfolios/live-gate/latest": (
            503,
            {"detail": "temporarily unavailable"},
        ),
    }

    monkeypatch.setattr(
        smoke,
        "_get",
        lambda _base_url, path: responses[path],
    )
    monkeypatch.setattr(smoke.sys, "argv", ["factor_portfolio_smoke.py"])

    assert smoke.main() == 0

    output = capsys.readouterr().out
    assert "[stage] live-gate decision" in output
    assert "[warn] live-gate snapshot unavailable: HTTP 503" in output


def test_main_returns_non_zero_when_triggered_run_finishes_with_error(monkeypatch, capsys):
    smoke = _load_smoke_module()

    monkeypatch.setattr(
        smoke,
        "_get",
        lambda _base_url, path: (
            200,
            {
                "status": "idle",
                "last_run_status": "success",
            },
        )
        if path == "/api/factor-research/status"
        else (_ for _ in ()).throw(AssertionError(path)),
    )
    monkeypatch.setattr(
        smoke,
        "_post",
        lambda _base_url, path, payload: (202, {"status": "started"})
        if path == "/api/factor-research/run"
        else (_ for _ in ()).throw(AssertionError(path)),
    )
    monkeypatch.setattr(
        smoke,
        "_wait_for_run_completion",
        lambda *_args: {
            "status": "idle",
            "last_run_status": "error",
            "last_error": "factor run crashed",
        },
    )
    monkeypatch.setattr(smoke.sys, "argv", ["factor_portfolio_smoke.py", "--trigger-run"])

    assert smoke.main() == 1

    output = capsys.readouterr().out
    assert "[error] latest run failed: factor run crashed" in output
