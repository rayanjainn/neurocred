from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from src.strategy.strategy_model import Strategy


class StrategyService:
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def add_strategy(self, user_id: str, strategy: Strategy) -> dict[str, Any]:
        payload = strategy.model_dump()
        await self.redis.lpush(f"strategy:{user_id}", json.dumps(payload, default=str))
        return payload

    async def get_strategies(self, user_id: str) -> list[dict[str, Any]]:
        data = await self.redis.lrange(f"strategy:{user_id}", 0, -1)
        strategies: list[dict[str, Any]] = []
        for item in data:
            try:
                strategies.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                continue
        return strategies
