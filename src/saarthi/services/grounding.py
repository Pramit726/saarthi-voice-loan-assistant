from __future__ import annotations

import json
from typing import Protocol

from saarthi.domain.contracts import (
    ApplicationDraft,
    GroundedAnswer,
    GroundedClaim,
)
from saarthi.domain.enums import SupportStatus, TurnRoute
from saarthi.providers.groq import GroqStructuredClient
from saarthi.providers.knowledge import KnowledgeProvider
from saarthi.services.calculator import FinancialCalculator, ProjectionUnavailable


class GroundedAnswerService:
    def __init__(
        self,
        knowledge: KnowledgeProvider,
        *,
        calculator: FinancialCalculator,
        writer: GroqStructuredClient | None = None,
        retrieval_limit: int = 5,
    ) -> None:
        self.knowledge = knowledge
        self.calculator = calculator
        self.writer = writer
        self.retrieval_limit = retrieval_limit

    async def answer(
        self,
        question: str,
        *,
        route: TurnRoute,
        draft: ApplicationDraft,
    ) -> GroundedAnswer:
        if route is TurnRoute.CALCULATION:
            return self._calculation_answer(question, draft)

        facts = await self.knowledge.retrieve(
            question,
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=draft.product_version,
            limit=self.retrieval_limit,
        )
        if not facts:
            return GroundedAnswer(
                product_id=draft.product_id,
                product_version=draft.product_version,
                fact_set_version=draft.product_version,
                question_route=route,
                support_status=SupportStatus.UNSUPPORTED,
                completeness_passed=False,
                abstention_reason="no_approved_fact",
            )

        selected = facts[:3]
        allowed_ids = {item.fact.fact_id for item in selected}
        if self.writer:
            system = """Answer only from the supplied approved facts. Keep spoken sentences short and neutral.
Return segments and the exact fact IDs used. Do not infer approval, advice, or a personalised offer.
If the evidence does not answer the question, return no segments and no IDs."""
            payload = await self.writer.word_grounded_answer(
                system=system,
                user=json.dumps(
                    {
                        "question": question,
                        "facts": [
                            {"fact_id": item.fact.fact_id, "text": item.fact.text}
                            for item in selected
                        ],
                    }
                ),
            )
            used_ids = set(payload.used_fact_ids)
            if payload.segments and used_ids and used_ids <= allowed_ids:
                return GroundedAnswer(
                    product_id=draft.product_id,
                    product_version=draft.product_version,
                    fact_set_version=draft.product_version,
                    question_route=route,
                    claims=[
                        GroundedClaim(text=segment, fact_ids=sorted(used_ids))
                        for segment in payload.segments
                    ],
                    supporting_fact_ids=sorted(used_ids),
                    support_status=SupportStatus.SUPPORTED,
                    completeness_passed=True,
                )

        top = selected[0].fact
        return GroundedAnswer(
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=draft.product_version,
            question_route=route,
            claims=[GroundedClaim(text=top.text, fact_ids=[top.fact_id])],
            supporting_fact_ids=[top.fact_id],
            support_status=SupportStatus.SUPPORTED,
            completeness_passed=True,
        )

    def _calculation_answer(self, question: str, draft: ApplicationDraft) -> GroundedAnswer:
        try:
            projection = self.calculator.calculate(draft)
        except ProjectionUnavailable as exc:
            return GroundedAnswer(
                product_id=draft.product_id,
                product_version=draft.product_version,
                fact_set_version=draft.product_version,
                question_route=TurnRoute.CALCULATION,
                support_status=SupportStatus.UNSUPPORTED,
                completeness_passed=False,
                abstention_reason=str(exc),
            )

        calculation_id = projection.projection_id
        lowered = question.casefold()
        if "receive" in lowered or "get" in lowered or "disburs" in lowered or "account" in lowered:
            text = f"The calculated net amount is Rs. {projection.net_disbursal}."
            labelled_values = {"net_disbursal": str(projection.net_disbursal)}
        elif "fee" in lowered or "deduct" in lowered:
            text = (
                f"The processing fee is Rs. {projection.processing_fee}, and the tax on that fee is "
                f"Rs. {projection.tax_on_processing_fee}."
            )
            labelled_values = {
                "processing_fee": str(projection.processing_fee),
                "tax_on_processing_fee": str(projection.tax_on_processing_fee),
            }
        else:
            text = (
                f"The calculated monthly EMI is Rs. {projection.emi} for "
                f"{projection.tenure_months} months."
            )
            labelled_values = {
                "emi": str(projection.emi),
                "tenure_months": str(projection.tenure_months),
            }
        return GroundedAnswer(
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=draft.product_version,
            question_route=TurnRoute.CALCULATION,
            claims=[GroundedClaim(text=text, calculation_ids=[calculation_id])],
            calculation_ids=[calculation_id],
            labelled_values=labelled_values,
            support_status=SupportStatus.SUPPORTED,
            completeness_passed=True,
        )
