from __future__ import annotations

from fastapi import APIRouter, Request

from src.strategy.strategy_model import AddStrategyRequest
from src.strategy.strategy_service import StrategyService

router = APIRouter(tags=["strategy"])


@router.post("/strategy/add")
async def add_strategy(body: AddStrategyRequest, request: Request) -> dict:
    service = StrategyService(request.app.state.redis)
    added = await service.add_strategy(body.user_id, body.strategy)
    return {"status": "ok", "strategy": added}


@router.get("/strategy/{user_id}")
async def get_strategies(user_id: str, request: Request) -> list[dict]:
    service = StrategyService(request.app.state.redis)
    strategies = await service.get_strategies(user_id)
    return strategies
