from __future__ import annotations

from pydantic import BaseModel, Field


class SkillExecuteRequest(BaseModel):
    action: str
    input: dict = Field(default_factory=dict)


class SkillExecuteResponse(BaseModel):
    action: str
    ok: bool
    data: dict
