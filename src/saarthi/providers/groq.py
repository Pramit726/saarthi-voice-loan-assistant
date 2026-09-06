from __future__ import annotations

import json
from typing import Any

from groq import AsyncGroq
from pydantic import BaseModel, ConfigDict


class InterpretationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acts: list[str]
    route: str
    target_field: str | None
    # JSON Schema represents both integer and float values as `number` for this
    # contract. Keeping both in a union is rejected by Groq as ambiguous.
    candidate_value: str | float | None
    source_span: str | None
    reference_resolution: str | None
    control: str | None
    uncertainty: float
    rationale_code: str
    explicit_write: bool


class GroundedWordingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segments: list[str]
    used_fact_ids: list[str]


class GroqStructuredClient:
    def __init__(self, *, api_key: str, model: str, timeout_seconds: float, temperature: float) -> None:
        self._client = AsyncGroq(api_key=api_key, timeout=timeout_seconds)
        self.model = model
        self.temperature = temperature

    async def structured(self, *, system: str, user: str, schema: type[BaseModel]) -> BaseModel:
        response = await self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__.lower(),
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        )
        content = response.choices[0].message.content or "{}"
        return schema.model_validate(json.loads(content))

    async def interpret(self, *, system: str, user: str) -> InterpretationPayload:
        result = await self.structured(system=system, user=user, schema=InterpretationPayload)
        return InterpretationPayload.model_validate(result)

    async def word_grounded_answer(self, *, system: str, user: str) -> GroundedWordingPayload:
        result = await self.structured(system=system, user=user, schema=GroundedWordingPayload)
        return GroundedWordingPayload.model_validate(result)

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close:
            result: Any = close()
            if hasattr(result, "__await__"):
                await result
