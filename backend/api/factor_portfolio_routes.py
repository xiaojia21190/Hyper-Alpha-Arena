from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.connection import get_db
from services.factor_portfolio_deployment_service import (
    deploy_portfolio_candidate,
    get_latest_live_gate_status,
    get_latest_portfolio_run,
    get_portfolio_run_detail,
    list_portfolio_deployments,
)

router = APIRouter(prefix="/api/factor-portfolios", tags=["factor-portfolios"])


class DeployPortfolioRequest(BaseModel):
    account_id: int = Field(gt=0)
    period: str = "1h"
    trigger_interval: int = Field(default=3600, ge=30)
    signal_pool_ids: list[int] = []
    exchange: str = "hyperliquid"
    confirm_live: bool = False


@router.get("/latest")
async def latest_factor_portfolio_run(db: Session = Depends(get_db)):
    payload = get_latest_portfolio_run(db)
    if payload is None:
        raise HTTPException(status_code=404, detail="No successful factor portfolio run found")
    return payload


@router.get("/live-gate/latest")
async def latest_live_gate_status(db: Session = Depends(get_db)):
    payload = get_latest_live_gate_status(db)
    if payload is None:
        raise HTTPException(status_code=404, detail="No successful factor research run found")
    return payload


@router.get("/runs/{run_id}")
async def factor_portfolio_run_detail(run_id: int, db: Session = Depends(get_db)):
    payload = get_portfolio_run_detail(db, run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Factor portfolio run not found: {run_id}")
    return payload


@router.get("/deployments")
async def factor_portfolio_deployments(
    account_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return {
        "items": list_portfolio_deployments(
            db,
            account_id=account_id,
            limit=limit,
        )
    }


@router.post("/{portfolio_id}/deploy-paper")
async def deploy_portfolio_paper(
    portfolio_id: int,
    request: DeployPortfolioRequest,
    db: Session = Depends(get_db),
):
    try:
        return deploy_portfolio_candidate(
            db,
            portfolio_id=portfolio_id,
            account_id=request.account_id,
            mode="paper",
            confirm_live=False,
            period=request.period,
            trigger_interval=request.trigger_interval,
            signal_pool_ids=request.signal_pool_ids,
            require_live_confirm=True,
            exchange=request.exchange,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{portfolio_id}/deploy-live")
async def deploy_portfolio_live(
    portfolio_id: int,
    request: DeployPortfolioRequest,
    db: Session = Depends(get_db),
):
    try:
        return deploy_portfolio_candidate(
            db,
            portfolio_id=portfolio_id,
            account_id=request.account_id,
            mode="live",
            confirm_live=request.confirm_live,
            period=request.period,
            trigger_interval=request.trigger_interval,
            signal_pool_ids=request.signal_pool_ids,
            require_live_confirm=True,
            exchange=request.exchange,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
