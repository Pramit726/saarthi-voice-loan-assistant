from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel

from saarthi.providers.groq import InterpretationPayload


class GeminiStructuredClient:
    """Minimal Gemini REST client for schema-constrained turn interpretation."""

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float) -> None:
        self.model = model.removeprefix("models/")
        self._client = httpx.AsyncClient(
            base_url="https://generativelanguage.googleapis.com/v1beta",
            headers={"x-goog-api-key": api_key},
            timeout=timeout_seconds,
            http2=True,
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
                keepalive_expiry=60.0,
            ),
        )

    async def structured(
        self, *, system: str, user: str, schema: type[BaseModel]
    ) -> BaseModel:
        response = await self._client.post(
            "/interactions",
            json={
                "model": self.model,
                "system_instruction": system,
                "input": user,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema.model_json_schema(),
                },
                "generation_config": {
                    "max_output_tokens": 384,
                    "thinking_level": "minimal",
                    "seed": 0,
                },
                "store": False,
            },
        )
        response.raise_for_status()
        body = response.json()
        try:
            output_steps = [
                step for step in body["steps"] if step.get("type") == "model_output"
            ]
            content = "".join(
                item.get("text", "")
                for step in output_steps
                for item in step.get("content", [])
                if item.get("type") == "text"
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("gemini_response_missing_content") from exc
        if not content:
            raise ValueError("gemini_response_empty_content")
        return schema.model_validate(json.loads(content))

    async def interpret(self, *, system: str, user: str) -> InterpretationPayload:
        result = await self.structured(
            system=system,
            user=user,
            schema=InterpretationPayload,
        )
        return InterpretationPayload.model_validate(result)

    async def close(self) -> None:
        result: Any = self._client.aclose()
        if hasattr(result, "__await__"):
            await result
