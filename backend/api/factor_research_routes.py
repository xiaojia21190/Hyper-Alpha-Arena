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
    request: ResearchRunRequest | None = None,
):
    payload = request or ResearchRunRequest()
    try:
        return factor_research_automation_service.trigger_run(
            exchange=payload.exchange,
            top_n_symbols=payload.top_n_symbols,
            lookback_days=payload.lookback_days,
            objective=payload.objective,
            factor_scope=payload.factor_scope,
            period=payload.period,
            prescreen_limit=payload.prescreen_limit,
            auto_promote_paper=payload.auto_promote_paper,
            paper_account_id=payload.paper_account_id,
            auto_promote_live=payload.auto_promote_live,
            live_account_id=payload.live_account_id,
            live_min_observation_hours=payload.live_min_observation_hours,
            live_min_trades=payload.live_min_trades,
            live_min_net_pnl=payload.live_min_net_pnl,
            live_min_win_rate=payload.live_min_win_rate,
            live_max_drawdown_percent=payload.live_max_drawdown_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
