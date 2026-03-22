from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from database.models import (
    Account,
    AccountAssetSnapshot,
    AccountProgramBinding,
    FactorPortfolioCandidate,
    FactorPortfolioDeployment,
    FactorResearchRun,
    ProgramExecutionLog,
    TradingProgram,
    User,
)
from services.factor_portfolio_service import build_weighted_portfolio_strategy_code

logger = logging.getLogger(__name__)


def _parse_json(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _to_utc_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _calculate_max_drawdown_percent(asset_values: list[float]) -> float:
    if not asset_values:
        return 0.0

    peak_value = max(float(asset_values[0]), 1e-12)
    max_drawdown = 0.0
    for current_value in asset_values:
        current_value = float(current_value)
        if current_value > peak_value:
            peak_value = current_value
            continue
        drawdown = ((peak_value - current_value) / max(peak_value, 1e-12)) * 100.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    return float(max_drawdown)


def _serialize_run(run: FactorResearchRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "exchange": run.exchange,
        "top_n_symbols": run.top_n_symbols,
        "lookback_days": run.lookback_days,
        "objective": run.objective,
        "factor_scope": run.factor_scope,
        "period": run.period,
        "prescreen_limit": run.prescreen_limit,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "top_factor": _parse_json(run.top_factor_json, None),
        "top_portfolio": _parse_json(run.top_portfolio_json, None),
    }


def _serialize_candidate(candidate: FactorPortfolioCandidate) -> dict[str, Any]:
    metrics = _parse_json(candidate.metrics_json, {})
    return {
        "id": candidate.id,
        "run_id": candidate.run_id,
        "name": candidate.name,
        "construction_method": candidate.construction_method,
        "score": candidate.score,
        "component_count": candidate.component_count,
        "weights": _parse_json(candidate.components_json, []),
        "metrics": metrics,
        "is_recommended": bool(candidate.is_recommended),
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }


def _serialize_deployment(row: FactorPortfolioDeployment) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "portfolio_id": row.portfolio_id,
        "account_id": row.account_id,
        "mode": row.mode,
        "status": row.status,
        "program_id": row.program_id,
        "binding_id": row.binding_id,
        "deployment_config": _parse_json(row.deployment_config, None),
        "deployment_result": _parse_json(row.deployment_result, None),
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class FactorPortfolioDeploymentService:
    def __init__(self, db):
        self.db = db

    def deploy_portfolio(
        self,
        portfolio_id: int,
        account_id: int,
        mode: str = "paper",
        confirm_live: bool = False,
        period: str = "1h",
        trigger_interval: int = 3600,
        signal_pool_ids: Optional[list[int]] = None,
        require_live_confirm: bool = True,
        exchange: str = "hyperliquid",
    ) -> dict[str, Any]:
        if mode not in {"paper", "live"}:
            raise ValueError(f"Unsupported deployment mode: {mode}")
        if mode == "live" and require_live_confirm and not confirm_live:
            raise ValueError("Live deployment requires confirm_live=true")

        account = self.db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise ValueError(f"Account not found: {account_id}")

        candidate = (
            self.db.query(FactorPortfolioCandidate)
            .filter(FactorPortfolioCandidate.id == portfolio_id)
            .first()
        )
        if not candidate:
            raise ValueError(f"Portfolio candidate not found: {portfolio_id}")

        weights = _parse_json(candidate.components_json, [])
        if not weights:
            raise ValueError("Portfolio candidate has no components")

        portfolio_payload = {
            "id": candidate.id,
            "name": candidate.name,
            "construction_method": candidate.construction_method,
            "weights": weights,
            "score": candidate.score,
        }
        code = build_weighted_portfolio_strategy_code(
            portfolio_payload,
            period=period,
        )

        user = self.db.query(User).filter(User.id == account.user_id).first()
        if not user:
            user = self.db.query(User).filter(User.username == "default").first()
        user_id = user.id if user else account.user_id

        program_name = (
            f"auto-portfolio-run-{candidate.run_id}-portfolio-{candidate.id}-{mode}"
        )
        description = (
            f"Auto-generated {mode} deployment for portfolio candidate #{candidate.id} "
            f"({candidate.construction_method})"
        )
        program = TradingProgram(
            user_id=user_id,
            name=program_name,
            description=description,
            code=code,
            params=_to_json(
                {
                    "portfolio_candidate_id": candidate.id,
                    "run_id": candidate.run_id,
                    "mode": mode,
                    "period": period,
                    "weights": weights,
                }
            ),
            icon="chart-no-axes-combined",
        )
        self.db.add(program)
        self.db.commit()
        self.db.refresh(program)

        signal_pool_ids = signal_pool_ids or []
        binding = AccountProgramBinding(
            account_id=account_id,
            program_id=program.id,
            signal_pool_ids=_to_json(signal_pool_ids) if signal_pool_ids else None,
            trigger_interval=max(int(trigger_interval), 30),
            scheduled_trigger_enabled=True,
            is_active=True,
            exchange=exchange,
        )
        self.db.add(binding)
        self.db.commit()
        self.db.refresh(binding)

        deployment = FactorPortfolioDeployment(
            run_id=candidate.run_id,
            portfolio_id=candidate.id,
            account_id=account_id,
            mode=mode,
            status="deployed",
            program_id=program.id,
            binding_id=binding.id,
            deployment_config=_to_json(
                {
                    "period": period,
                    "trigger_interval": max(int(trigger_interval), 30),
                    "signal_pool_ids": signal_pool_ids,
                    "exchange": exchange,
                    "confirm_live": bool(confirm_live),
                }
            ),
            deployment_result=_to_json(
                {
                    "program_name": program.name,
                    "binding_id": binding.id,
                }
            ),
        )
        self.db.add(deployment)
        self.db.commit()
        self.db.refresh(deployment)

        return {
            "deployment": _serialize_deployment(deployment),
            "program": {
                "id": program.id,
                "name": program.name,
            },
            "binding": {
                "id": binding.id,
                "account_id": binding.account_id,
                "program_id": binding.program_id,
            },
            "portfolio": _serialize_candidate(candidate),
        }

    def _resolve_paper_gate_context(
        self,
        portfolio_id: int,
        paper_account_id: int,
        paper_deployment_id: int | None = None,
    ) -> dict[str, Any] | None:
        query = self.db.query(FactorPortfolioDeployment).filter(
            FactorPortfolioDeployment.portfolio_id == portfolio_id,
            FactorPortfolioDeployment.account_id == paper_account_id,
            FactorPortfolioDeployment.mode == "paper",
            FactorPortfolioDeployment.status == "deployed",
        )
        if paper_deployment_id is not None:
            query = query.filter(FactorPortfolioDeployment.id == int(paper_deployment_id))
        paper_deployment = (
            query.order_by(
                FactorPortfolioDeployment.created_at.desc(),
                FactorPortfolioDeployment.id.desc(),
            ).first()
        )
        if paper_deployment is None:
            return None

        observation_start = paper_deployment.created_at
        observation_start_utc = _to_utc_timestamp(observation_start)
        observation_hours = 0.0
        if observation_start_utc is not None:
            observation_hours = max(
                (datetime.now(timezone.utc) - observation_start_utc).total_seconds() / 3600.0,
                0.0,
            )

        logs_query = self.db.query(ProgramExecutionLog).filter(
            ProgramExecutionLog.account_id == int(paper_account_id),
            ProgramExecutionLog.success,
            ProgramExecutionLog.decision_action.in_(["buy", "sell", "close"]),
            ProgramExecutionLog.realized_pnl.isnot(None),
            ProgramExecutionLog.realized_pnl != 0,
        )
        if paper_deployment.program_id is not None:
            logs_query = logs_query.filter(
                ProgramExecutionLog.program_id == paper_deployment.program_id
            )
        if paper_deployment.binding_id is not None:
            logs_query = logs_query.filter(
                ProgramExecutionLog.binding_id == paper_deployment.binding_id
            )
        if observation_start is not None:
            logs_query = logs_query.filter(
                ProgramExecutionLog.created_at >= observation_start
            )
        execution_logs = (
            logs_query.order_by(
                ProgramExecutionLog.created_at.asc(),
                ProgramExecutionLog.id.asc(),
            ).all()
        )
        pnl_values = [float(row.realized_pnl) for row in execution_logs]
        trade_count = len(pnl_values)
        winning_trades = sum(1 for pnl in pnl_values if pnl > 0)
        win_rate_percent = (winning_trades / trade_count * 100.0) if trade_count else 0.0
        net_pnl = sum(pnl_values)

        snapshots_query = self.db.query(AccountAssetSnapshot).filter(
            AccountAssetSnapshot.account_id == int(paper_account_id),
        )
        if observation_start is not None:
            snapshots_query = snapshots_query.filter(
                AccountAssetSnapshot.event_time >= observation_start
            )
        snapshots = (
            snapshots_query.order_by(
                AccountAssetSnapshot.event_time.asc(),
                AccountAssetSnapshot.id.asc(),
            ).all()
        )
        asset_values = [float(row.total_assets) for row in snapshots]
        max_drawdown_percent = _calculate_max_drawdown_percent(asset_values)

        return {
            "paper_deployment": paper_deployment,
            "observation_hours": float(observation_hours),
            "trade_count": int(trade_count),
            "winning_trades": int(winning_trades),
            "win_rate_percent": float(win_rate_percent),
            "net_pnl": float(net_pnl),
            "max_drawdown_percent": float(max_drawdown_percent),
        }

    def _find_existing_live_deployment(
        self,
        portfolio_id: int,
        live_account_id: int,
    ) -> FactorPortfolioDeployment | None:
        return (
            self.db.query(FactorPortfolioDeployment)
            .filter(
                FactorPortfolioDeployment.portfolio_id == portfolio_id,
                FactorPortfolioDeployment.account_id == live_account_id,
                FactorPortfolioDeployment.mode == "live",
                FactorPortfolioDeployment.status == "deployed",
            )
            .order_by(
                FactorPortfolioDeployment.created_at.desc(),
                FactorPortfolioDeployment.id.desc(),
            )
            .first()
        )

    def auto_decide_live_promotion(
        self,
        portfolio_id: int,
        paper_account_id: int,
        live_account_id: int,
        *,
        min_observation_hours: float = 24.0,
        min_trades: int = 10,
        min_net_pnl: float = 0.0,
        min_win_rate: float = 50.0,
        max_drawdown_percent_limit: float = 20.0,
        period: str = "1h",
        trigger_interval: int = 3600,
        signal_pool_ids: Optional[list[int]] = None,
        require_live_confirm: bool = True,
        exchange: str = "hyperliquid",
        paper_deployment_id: int | None = None,
    ) -> dict[str, Any]:
        if int(live_account_id or 0) <= 0:
            return {
                "decision": "skipped",
                "reason": "invalid_live_account_id",
                "gate": None,
                "paper_context": None,
                "live_deployment": None,
            }

        context = self._resolve_paper_gate_context(
            portfolio_id=portfolio_id,
            paper_account_id=paper_account_id,
            paper_deployment_id=paper_deployment_id,
        )
        if context is None:
            return {
                "decision": "not_ready",
                "reason": "paper_deployment_not_found",
                "gate": None,
                "paper_context": None,
                "live_deployment": None,
            }

        checks = {
            "observation_hours": {
                "actual": round(float(context["observation_hours"]), 6),
                "threshold": float(min_observation_hours),
                "passed": float(context["observation_hours"]) >= float(min_observation_hours),
            },
            "trade_count": {
                "actual": int(context["trade_count"]),
                "threshold": int(min_trades),
                "passed": int(context["trade_count"]) >= int(min_trades),
            },
            "net_pnl": {
                "actual": round(float(context["net_pnl"]), 6),
                "threshold": float(min_net_pnl),
                "passed": float(context["net_pnl"]) >= float(min_net_pnl),
            },
            "win_rate_percent": {
                "actual": round(float(context["win_rate_percent"]), 6),
                "threshold": float(min_win_rate),
                "passed": float(context["win_rate_percent"]) >= float(min_win_rate),
            },
            "max_drawdown_percent": {
                "actual": round(float(context["max_drawdown_percent"]), 6),
                "threshold": float(max_drawdown_percent_limit),
                "passed": float(context["max_drawdown_percent"]) <= float(max_drawdown_percent_limit),
            },
        }
        failed_checks = [
            name for name, payload in checks.items() if not bool(payload["passed"])
        ]
        gate = {
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "checks": checks,
        }
        paper_context = {
            "paper_account_id": int(paper_account_id),
            "portfolio_id": int(portfolio_id),
            "paper_deployment": _serialize_deployment(context["paper_deployment"]),
            "metrics": {
                "observation_hours": checks["observation_hours"]["actual"],
                "trade_count": checks["trade_count"]["actual"],
                "winning_trades": int(context["winning_trades"]),
                "net_pnl": checks["net_pnl"]["actual"],
                "win_rate_percent": checks["win_rate_percent"]["actual"],
                "max_drawdown_percent": checks["max_drawdown_percent"]["actual"],
            },
        }

        if not gate["passed"]:
            return {
                "decision": "not_ready",
                "reason": "gate_not_passed",
                "gate": gate,
                "paper_context": paper_context,
                "live_deployment": None,
            }

        existing_live = self._find_existing_live_deployment(
            portfolio_id=portfolio_id,
            live_account_id=live_account_id,
        )
        if existing_live is not None:
            return {
                "decision": "skipped",
                "reason": "already_live_for_target_account",
                "gate": gate,
                "paper_context": paper_context,
                "live_deployment": {
                    "deployment": _serialize_deployment(existing_live),
                    "already_exists": True,
                },
            }

        try:
            live_deployment = self.deploy_portfolio(
                portfolio_id=portfolio_id,
                account_id=live_account_id,
                mode="live",
                confirm_live=True,
                period=period,
                trigger_interval=trigger_interval,
                signal_pool_ids=signal_pool_ids,
                require_live_confirm=require_live_confirm,
                exchange=exchange,
            )
        except Exception as exc:
            logger.exception(
                "[FactorPortfolioDeployment] Auto live promotion failed for portfolio_id=%s",
                portfolio_id,
            )
            return {
                "decision": "error",
                "reason": "live_deployment_failed",
                "error": str(exc),
                "gate": gate,
                "paper_context": paper_context,
                "live_deployment": None,
            }

        return {
            "decision": "promoted",
            "reason": "gate_passed",
            "gate": gate,
            "paper_context": paper_context,
            "live_deployment": live_deployment,
        }


def get_latest_portfolio_run(db) -> dict[str, Any] | None:
    run = (
        db.query(FactorResearchRun)
        .filter(FactorResearchRun.status == "success")
        .order_by(FactorResearchRun.created_at.desc(), FactorResearchRun.id.desc())
        .first()
    )
    if not run:
        return None

    candidates = (
        db.query(FactorPortfolioCandidate)
        .filter(FactorPortfolioCandidate.run_id == run.id)
        .order_by(FactorPortfolioCandidate.score.desc(), FactorPortfolioCandidate.id.asc())
        .all()
    )
    serialized_candidates = [_serialize_candidate(candidate) for candidate in candidates]
    top_portfolio = next(
        (candidate for candidate in serialized_candidates if candidate.get("is_recommended")),
        serialized_candidates[0] if serialized_candidates else None,
    )
    return {
        "run": _serialize_run(run),
        "portfolio_candidates": serialized_candidates,
        "top_portfolio": top_portfolio,
    }


def get_portfolio_run_detail(db, run_id: int) -> dict[str, Any] | None:
    run = db.query(FactorResearchRun).filter(FactorResearchRun.id == run_id).first()
    if not run:
        return None
    candidates = (
        db.query(FactorPortfolioCandidate)
        .filter(FactorPortfolioCandidate.run_id == run.id)
        .order_by(FactorPortfolioCandidate.score.desc(), FactorPortfolioCandidate.id.asc())
        .all()
    )
    deployments = (
        db.query(FactorPortfolioDeployment)
        .filter(FactorPortfolioDeployment.run_id == run.id)
        .order_by(FactorPortfolioDeployment.created_at.desc(), FactorPortfolioDeployment.id.desc())
        .all()
    )
    serialized_candidates = [_serialize_candidate(candidate) for candidate in candidates]
    top_portfolio = next(
        (candidate for candidate in serialized_candidates if candidate.get("is_recommended")),
        serialized_candidates[0] if serialized_candidates else None,
    )
    return {
        "run": _serialize_run(run),
        "portfolio_candidates": serialized_candidates,
        "top_portfolio": top_portfolio,
        "deployments": [_serialize_deployment(row) for row in deployments],
    }


def list_portfolio_deployments(
    db,
    account_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = db.query(FactorPortfolioDeployment)
    if account_id is not None:
        query = query.filter(FactorPortfolioDeployment.account_id == account_id)
    rows = (
        query.order_by(
            FactorPortfolioDeployment.created_at.desc(),
            FactorPortfolioDeployment.id.desc(),
        )
        .limit(max(int(limit), 1))
        .all()
    )
    return [_serialize_deployment(row) for row in rows]


def deploy_portfolio_candidate(
    db,
    portfolio_id: int,
    account_id: int,
    mode: str,
    confirm_live: bool = False,
    period: str = "1h",
    trigger_interval: int = 3600,
    signal_pool_ids: Optional[list[int]] = None,
    require_live_confirm: bool = True,
    exchange: str = "hyperliquid",
) -> dict[str, Any]:
    service = FactorPortfolioDeploymentService(db)
    return service.deploy_portfolio(
        portfolio_id=portfolio_id,
        account_id=account_id,
        mode=mode,
        confirm_live=confirm_live,
        period=period,
        trigger_interval=trigger_interval,
        signal_pool_ids=signal_pool_ids,
        require_live_confirm=require_live_confirm,
        exchange=exchange,
    )


def auto_decide_live_promotion(
    db,
    portfolio_id: int,
    paper_account_id: int,
    live_account_id: int,
    *,
    min_observation_hours: float = 24.0,
    min_trades: int = 10,
    min_net_pnl: float = 0.0,
    min_win_rate: float = 50.0,
    max_drawdown_percent_limit: float = 20.0,
    period: str = "1h",
    trigger_interval: int = 3600,
    signal_pool_ids: Optional[list[int]] = None,
    require_live_confirm: bool = True,
    exchange: str = "hyperliquid",
    paper_deployment_id: int | None = None,
) -> dict[str, Any]:
    service = FactorPortfolioDeploymentService(db)
    return service.auto_decide_live_promotion(
        portfolio_id=portfolio_id,
        paper_account_id=paper_account_id,
        live_account_id=live_account_id,
        min_observation_hours=min_observation_hours,
        min_trades=min_trades,
        min_net_pnl=min_net_pnl,
        min_win_rate=min_win_rate,
        max_drawdown_percent_limit=max_drawdown_percent_limit,
        period=period,
        trigger_interval=trigger_interval,
        signal_pool_ids=signal_pool_ids,
        require_live_confirm=require_live_confirm,
        exchange=exchange,
        paper_deployment_id=paper_deployment_id,
    )
