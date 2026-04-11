from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Strategy(BaseModel):
    strategy_id: str
    user_id: str
    created_by: str
    title: str
    description: str
    steps: list[Any] = Field(default_factory=list)
    impact: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class AddStrategyRequest(BaseModel):
    user_id: str
    strategy: Strategy
