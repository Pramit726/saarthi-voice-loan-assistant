from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from functools import lru_cache

from fastembed import TextEmbedding

from saarthi.domain.enums import FieldId

_PURPOSE_PROTOTYPES: dict[str, str] = {
    "education": (
        "education tuition school college university coaching classes course fees studies"
    ),
    "medical expenses": (
        "medical treatment hospital surgery medicine healthcare doctor bills"
    ),
    "home renovation": (
        "home renovation house repairs roof plumbing construction water tank improvement"
    ),
    "wedding": "wedding marriage ceremony expenses",
    "travel": "travel trip holiday vacation journey expenses",
    "debt consolidation": (
        "debt consolidation repay credit cards clear existing loan dues"
    ),
    "vehicle purchase": "buy vehicle car bike motorcycle scooter",
    "business expenses": (
        "business working capital inventory equipment expand shop commercial expenses"
    ),
    "consumer purchase": (
        "buy laptop computer appliance washing machine electronics furniture"
    ),
    "personal expenses": (
        "personal family household emergency general personal expenses"
    ),
}

_EMPLOYMENT_PROTOTYPES: dict[str, str] = {
    "salaried": (
        "salaried employee payroll monthly salary work for a company employer government job"
    ),
    "self-employed": (
        "self employed own business entrepreneur freelancer consultant contractor run a shop"
    ),
}

_PROTOTYPES: dict[FieldId, dict[str, str]] = {
    FieldId.LOAN_PURPOSE: _PURPOSE_PROTOTYPES,
    FieldId.EMPLOYMENT_TYPE: _EMPLOYMENT_PROTOTYPES,
}


@dataclass(frozen=True)
class SemanticFieldCandidate:
    value: str
    score: float
    margin: float
    source: str = "local_embedding"


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


@lru_cache(maxsize=4)
def _model_and_prototypes(
    model_name: str,
) -> tuple[TextEmbedding, dict[FieldId, dict[str, list[float]]]]:
    model = TextEmbedding(model_name=model_name)
    labels: list[tuple[FieldId, str]] = []
    texts: list[str] = []
    for field_id, choices in _PROTOTYPES.items():
        for value, prototype in choices.items():
            labels.append((field_id, value))
            texts.append(prototype)
    vectors = [_unit(vector.tolist()) for vector in model.embed(texts)]
    indexed: dict[FieldId, dict[str, list[float]]] = {}
    for (field_id, value), vector in zip(labels, vectors, strict=True):
        indexed.setdefault(field_id, {})[value] = vector
    return model, indexed


class SemanticFieldResolver:
    """Conservative local classifier for bounded form fields.

    It proposes an allowed enum value only when both absolute similarity and
    separation from the runner-up are strong. The caller must still ask the
    borrower to confirm the proposal before committing it.
    """

    def __init__(
        self,
        *,
        model_name: str,
        minimum_score: float = 0.62,
        minimum_margin: float = 0.07,
    ) -> None:
        self.model_name = model_name
        self.minimum_score = minimum_score
        self.minimum_margin = minimum_margin

    async def resolve(
        self, field_id: FieldId, text: str
    ) -> SemanticFieldCandidate | None:
        if field_id not in _PROTOTYPES:
            return None
        return await asyncio.to_thread(self._resolve_sync, field_id, text)

    def _resolve_sync(
        self, field_id: FieldId, text: str
    ) -> SemanticFieldCandidate | None:
        model, prototypes = _model_and_prototypes(self.model_name)
        query = _unit(next(model.embed([text])).tolist())
        ranked = sorted(
            (
                (value, _cosine(query, prototype))
                for value, prototype in prototypes[field_id].items()
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        best_value, best_score = ranked[0]
        second_score = ranked[1][1]
        margin = best_score - second_score
        if best_score < self.minimum_score or margin < self.minimum_margin:
            return None
        return SemanticFieldCandidate(
            value=best_value,
            score=best_score,
            margin=margin,
        )
