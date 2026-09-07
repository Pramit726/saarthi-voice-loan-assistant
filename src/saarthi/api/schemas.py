from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from saarthi.domain.enums import ControlCommand, DeliveryStatus


class SessionCreateResponse(BaseModel):
    session_id: str
    application_id: str
    participant_id: str
    trace_id: str
    room_name: str
    pending_field: str | None
    opening_prompt: str
    language: str = "en-IN"
    synthetic: bool = True
    terminal_outcome: str = "reviewable draft only"


class SessionCreateRequest(BaseModel):
    language: Literal["en-IN", "hi-IN"] = "en-IN"


class TokenRequest(BaseModel):
    session_id: str


class TokenResponse(BaseModel):
    url: str
    token: str
    room_name: str
    participant_identity: str


class TextTurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    confidence: float | None = Field(default=1.0, ge=0, le=1)
    language: str = "en-IN"


class ControlRequest(BaseModel):
    command: ControlCommand


class DeliveryUpdate(BaseModel):
    segment_id: str
    status: DeliveryStatus
    heard_character_count: int = Field(default=0, ge=0)


class StopLatencyRequest(BaseModel):
    latency_ms: float = Field(ge=0, le=60_000)
