from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.factor_research_service import (
    factor_research_automation_service,
)

router = APIRouter(prefix="/api/factor-research", tags=["factor-research"])


class ResearchRunRequest(BaseModel):
    exchange: str = "hyperliquid"
    top_n_symbols: int = Field(default=20, gt=0)
    lookback_days: int = Field(default=180, gt=0)
    objective: str = "return_over_drawdown"
    factor_scope: str = "builtin_only"
    period: str = "1h"
    prescreen_limit: int = Field(default=10, ge=0)
    auto_promote_paper: bool = False
    paper_account_id: int = Field(default=0, ge=0)
    auto_promote_live: bool = False
    live_account_id: int = Field(default=0, ge=0)
    live_min_observation_hours: float = Field(default=24.0, ge=0)
    live_min_trades: int = Field(default=10, ge=0)
    live_min_net_pnl: float = 0.0
    live_min_win_rate: float = Field(default=50.0, ge=0, le=100)
    live_max_drawdown_percent: float = Field(default=20.0, ge=0)


@router.get("/status")
async def get_factor_research_status():
    return factor_research_automation_service.get_status()


@router.post("/run", status_code=202)
async def run_factor_research(
    request: ResearchRunRequest,
):
    try:
        return factor_research_automation_service.trigger_run(
            exchange=request.exchange,
            top_n_symbols=request.top_n_symbols,
            lookback_days=request.lookback_days,
            objective=request.objective,
            factor_scope=request.factor_scope,
            period=request.period,
            prescreen_limit=request.prescreen_limit,
            auto_promote_paper=request.auto_promote_paper,
            paper_account_id=request.paper_account_id,
            auto_promote_live=request.auto_promote_live,
            live_account_id=request.live_account_id,
            live_min_observation_hours=request.live_min_observation_hours,
            live_min_trades=request.live_min_trades,
            live_min_net_pnl=request.live_min_net_pnl,
            live_min_win_rate=request.live_min_win_rate,
            live_max_drawdown_percent=request.live_max_drawdown_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
