#!/usr/bin/env python3
"""
Factor portfolio API smoke runner.

Safe defaults:
- read-only checks only
- optional research trigger
- optional paper deployment (never live by default)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STATUS_PATH = "/api/factor-research/status"
RUN_PATH = "/api/factor-research/run"
LATEST_PORTFOLIO_PATH = "/api/factor-portfolios/latest"
DEPLOYMENTS_PATH = "/api/factor-portfolios/deployments?limit=5"
LIVE_GATE_PATH = "/api/factor-portfolios/live-gate/latest"


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            body = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else "{}"
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return exc.code, parsed
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def _get(base_url: str, path: str) -> tuple[int, dict[str, Any]]:
    return _request_json("GET", f"{base_url.rstrip('/')}{path}")


def _post(base_url: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return _request_json("POST", f"{base_url.rstrip('/')}{path}", payload=payload)


def _wait_for_run_completion(base_url: str, timeout_seconds: int, poll_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status: dict[str, Any] | None = None
    while time.time() < deadline:
        code, body = _get(base_url, STATUS_PATH)
        if code != 200:
            raise RuntimeError(f"Status polling failed: HTTP {code} {body}")
        last_status = body
        if body.get("status") == "idle" and body.get("last_run_status") in {"success", "error"}:
            return body
        time.sleep(max(poll_seconds, 1))
    raise RuntimeError(f"Timed out waiting for run completion. Last status: {last_status}")


def _print_stage(name: str) -> None:
    print(f"[stage] {name}")


def _print_kv(prefix: str, **values: Any) -> None:
    fields = [f"{key}={values[key]}" for key in values if values[key] is not None]
    if fields:
        print(prefix, " ".join(fields))
        return
    print(prefix)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-check factor portfolio workflow APIs")
    parser.add_argument("--base-url", default="http://localhost:5611", help="Backend base URL")
    parser.add_argument("--trigger-run", action="store_true", help="Trigger /api/factor-research/run and wait")
    parser.add_argument("--top-n-symbols", type=int, default=20)
    parser.add_argument("--lookback-days", type=int, default=180)
    parser.add_argument("--period", default="1h")
    parser.add_argument("--prescreen-limit", type=int, default=10)
    parser.add_argument("--objective", default="return_over_drawdown")
    parser.add_argument("--factor-scope", default="builtin_only")
    parser.add_argument("--wait-timeout", type=int, default=1200)
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument(
        "--deploy-paper-account-id",
        type=int,
        default=0,
        help="Optional account_id for deploy-paper. 0 disables deployment.",
    )
    return parser.parse_args()


def _report_research_status(status_body: dict[str, Any]) -> None:
    _print_stage("research status")
    _print_kv(
        "[ok]",
        status=status_body.get("status"),
        last_run_status=status_body.get("last_run_status"),
        phase=(status_body.get("progress") or {}).get("phase"),
        completed_at=status_body.get("last_run_completed_at"),
    )


def _trigger_run_if_requested(args: argparse.Namespace, base_url: str) -> int:
    if not args.trigger_run:
        return 0

    run_payload = {
        "exchange": "hyperliquid",
        "top_n_symbols": args.top_n_symbols,
        "lookback_days": args.lookback_days,
        "objective": args.objective,
        "factor_scope": args.factor_scope,
        "period": args.period,
        "prescreen_limit": args.prescreen_limit,
        "auto_promote_paper": False,
        "paper_account_id": 0,
    }
    code, run_body = _post(base_url, RUN_PATH, run_payload)
    if code not in {200, 202}:
        print(f"[error] POST {RUN_PATH} -> HTTP {code}: {run_body}")
        return 1
    _print_kv("[ok]", trigger_status=run_body.get("status"))
    try:
        completed = _wait_for_run_completion(base_url, args.wait_timeout, args.poll_seconds)
    except RuntimeError as exc:
        print(f"[error] {exc}")
        return 1
    _print_kv(
        "[ok]",
        run_status=completed.get("last_run_status"),
        completed_at=completed.get("last_run_completed_at"),
    )
    if completed.get("last_run_status") != "success":
        print(f"[error] latest run failed: {completed.get('last_error')}")
        return 1
    return 0


def _report_latest_portfolio(base_url: str) -> tuple[int | None, int | None, int]:
    _print_stage("latest portfolio")
    code, latest_body = _get(base_url, LATEST_PORTFOLIO_PATH)
    if code == 404:
        print("[warn] no successful factor portfolio run found yet")
        return None, None, 0
    if code != 200:
        print(f"[error] GET {LATEST_PORTFOLIO_PATH} -> HTTP {code}: {latest_body}")
        return None, None, 1

    top_portfolio = latest_body.get("top_portfolio") or {}
    portfolio_id = top_portfolio.get("portfolio_id") or top_portfolio.get("id")
    run = latest_body.get("run") or {}
    run_id = run.get("id")
    candidate_count = _report_run_detail(base_url, run_id)
    _print_kv(
        "[ok]",
        run_id=run_id,
        run_status=run.get("status"),
        portfolio_id=portfolio_id,
        name=top_portfolio.get("name"),
        candidate_count=candidate_count,
    )
    return run_id, portfolio_id, 0


def _report_run_detail(base_url: str, run_id: int | None) -> int | None:
    if not run_id:
        return None
    detail_code, detail_body = _get(base_url, f"/api/factor-portfolios/runs/{run_id}")
    if detail_code == 200:
        return len(detail_body.get("portfolio_candidates") or [])
    print(f"[warn] run detail fetch failed: HTTP {detail_code} {detail_body}")
    return None


def _report_deployments(base_url: str) -> None:
    _print_stage("deployment summary")
    dep_code, dep_body = _get(base_url, DEPLOYMENTS_PATH)
    if dep_code != 200:
        print(f"[warn] deployment list failed: HTTP {dep_code} {dep_body}")
        return

    items = dep_body.get("items") or []
    paper_count = sum(1 for item in items if item.get("mode") == "paper")
    live_count = sum(1 for item in items if item.get("mode") == "live")
    deployed_count = sum(1 for item in items if item.get("status") == "deployed")
    _print_kv(
        "[ok]",
        total=len(items),
        paper=paper_count,
        live=live_count,
        deployed=deployed_count,
    )


def _report_live_gate(base_url: str) -> None:
    _print_stage("live-gate decision")
    live_code, live_body = _get(base_url, LIVE_GATE_PATH)
    if live_code != 200:
        print(f"[warn] live-gate snapshot unavailable: HTTP {live_code} {live_body}")
        return

    live_decision = live_body.get("live_decision") or {}
    latest_run = live_body.get("latest_run") or {}
    decision_run = live_body.get("decision_run") or {}
    if not live_decision:
        print("[warn] live-gate snapshot has no decision yet")
        return
    _print_kv(
        "[ok]",
        decision=live_decision.get("decision"),
        reason=live_decision.get("reason"),
        latest_run_id=latest_run.get("id"),
        decision_run_id=decision_run.get("id"),
    )


def _deploy_paper_if_requested(
    args: argparse.Namespace,
    base_url: str,
    portfolio_id: int | None,
) -> int:
    if args.deploy_paper_account_id <= 0:
        return 0
    if not portfolio_id:
        print("[error] cannot deploy paper: portfolio_id missing in latest payload")
        return 1

    payload = {
        "account_id": args.deploy_paper_account_id,
        "period": args.period,
        "trigger_interval": 3600,
        "signal_pool_ids": [],
        "exchange": "hyperliquid",
    }
    deploy_code, deploy_body = _post(
        base_url,
        f"/api/factor-portfolios/{int(portfolio_id)}/deploy-paper",
        payload,
    )
    if deploy_code != 200:
        print(f"[error] deploy-paper failed: HTTP {deploy_code} {deploy_body}")
        return 1

    deployment = deploy_body.get("deployment") or {}
    _print_kv(
        "[ok]",
        deploy_id=deployment.get("id"),
        mode=deployment.get("mode"),
        status=deployment.get("status"),
    )
    return 0


def main() -> int:
    args = _parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"[smoke] base_url={base_url}")

    code, status_body = _get(base_url, STATUS_PATH)
    if code != 200:
        print(f"[error] GET {STATUS_PATH} -> HTTP {code}: {status_body}")
        return 1
    _report_research_status(status_body)

    trigger_code = _trigger_run_if_requested(args, base_url)
    if trigger_code:
        return trigger_code

    _, portfolio_id, latest_code = _report_latest_portfolio(base_url)
    if latest_code:
        return latest_code

    _report_deployments(base_url)
    _report_live_gate(base_url)

    deploy_code = _deploy_paper_if_requested(args, base_url, portfolio_id)
    if deploy_code:
        return deploy_code

    print("[done] canonical factor portfolio smoke checks completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
