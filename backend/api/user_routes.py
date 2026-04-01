from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import User, UserExchangeConfig

router = APIRouter(prefix="/api/users", tags=["users"])

ExchangeId = Literal["hyperliquid", "binance", "aster"]


class ExchangeConfigUpdateRequest(BaseModel):
    selected_exchange: ExchangeId


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_or_create_default_user(db: Session) -> User:
    user = db.query(User).filter(User.username == "default").first()
    if user is not None:
        return user

    user = User(
        username="default",
        email=None,
        password_hash=None,
        is_active="true",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_exchange_config(db: Session, user_id: int) -> UserExchangeConfig:
    config = db.query(UserExchangeConfig).filter(UserExchangeConfig.user_id == user_id).first()
    if config is not None:
        return config

    config = UserExchangeConfig(user_id=user_id, selected_exchange="hyperliquid")
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("/exchange-config")
async def get_exchange_config(db: Session = Depends(get_db)):
    try:
        user = _get_or_create_default_user(db)
        config = _get_or_create_exchange_config(db, user.id)
        return {"selected_exchange": config.selected_exchange}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load exchange config: {exc}") from exc


@router.post("/exchange-config")
async def update_exchange_config(
    payload: ExchangeConfigUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        user = _get_or_create_default_user(db)
        config = _get_or_create_exchange_config(db, user.id)
        config.selected_exchange = payload.selected_exchange
        db.commit()
        db.refresh(config)
        return {"selected_exchange": config.selected_exchange}
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update exchange config: {exc}") from exc
