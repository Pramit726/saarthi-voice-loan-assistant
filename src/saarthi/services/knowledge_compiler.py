from __future__ import annotations

import re
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from saarthi.domain.contracts import ProductFact
from saarthi.providers.groq import GroqStructuredClient


class NumericCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    value: float


class FactCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id_hint: str
    fact_type: str
    topic: str
    text: str
    aliases: list[str]
    numeric_values: list[NumericCandidate]
    source_section: str


class CompilationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[FactCandidate]


class KnowledgeCompiler:
    """Converts free-form product prose into reviewable atomic candidates.

    Compilation never approves or publishes facts. Human-reviewed IDs must be
    explicitly approved before the ingestion script will put them in Qdrant.
    """

    def __init__(self, client: GroqStructuredClient) -> None:
        self.client = client

    async def propose(
        self,
        source_text: str,
        *,
        product_id: str,
        product_version: str,
        fact_set_version: str,
    ) -> list[ProductFact]:
        if len(source_text) > 24000:
            raise ValueError("Source must be chunked into sections of at most 24,000 characters.")
        result = await self.client.structured(
            system="""Convert the supplied fictional product sheet into atomic factual candidates.
Each candidate must express one independently retrievable product rule, definition, cost, condition,
illustration, or safety boundary. Preserve numbers exactly. Do not infer missing information.
Return draft candidates only; approval happens outside the model.""",
            user=source_text,
            schema=CompilationPayload,
        )
        payload = CompilationPayload.model_validate(result)
        facts: list[ProductFact] = []
        for index, candidate in enumerate(payload.facts, start=1):
            hint = re.sub(r"[^A-Z0-9-]", "-", candidate.fact_id_hint.upper()).strip("-")
            fact_id = f"{hint or 'SPL-COMPILED'}-{index:03d}"
            facts.append(
                ProductFact(
                    fact_id=fact_id,
                    product_id=product_id,
                    product_version=product_version,
                    fact_set_version=fact_set_version,
                    status="draft",
                    fact_type=candidate.fact_type,
                    topic=candidate.topic,
                    text=candidate.text,
                    aliases=candidate.aliases,
                    numeric_values={item.label: Decimal(str(item.value)) for item in candidate.numeric_values},
                    source_section=candidate.source_section,
                )
            )
        self.validate_candidates(facts)
        return facts

    @staticmethod
    def validate_candidates(facts: list[ProductFact]) -> None:
        identifiers = [fact.fact_id for fact in facts]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Fact IDs must be unique.")
        for fact in facts:
            if fact.status not in {"draft", "approved"}:
                raise ValueError(f"Invalid status for {fact.fact_id}.")
            if not fact.text.strip() or not fact.topic.strip() or not fact.source_section.strip():
                raise ValueError(f"Fact {fact.fact_id} is incomplete.")

    @staticmethod
    def approve(facts: list[ProductFact], *, approved_ids: set[str]) -> list[ProductFact]:
        unknown = approved_ids - {fact.fact_id for fact in facts}
        if unknown:
            raise ValueError(f"Unknown fact IDs: {sorted(unknown)}")
        return [
            fact.model_copy(update={"status": "approved" if fact.fact_id in approved_ids else "draft"})
            for fact in facts
        ]
