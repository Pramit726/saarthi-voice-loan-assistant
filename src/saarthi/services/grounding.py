from __future__ import annotations

import json
import re
from decimal import Decimal

from saarthi.domain.contracts import (
    ApplicationDraft,
    GroundedAnswer,
    GroundedClaim,
)
from saarthi.domain.enums import SupportStatus, TurnRoute
from saarthi.providers.groq import GroqStructuredClient
from saarthi.providers.knowledge import KnowledgeProvider
from saarthi.services.calculator import FinancialCalculator, ProjectionUnavailable

NUMBER_WORDS = {
    "one": Decimal(1),
    "two": Decimal(2),
    "three": Decimal(3),
    "four": Decimal(4),
    "five": Decimal(5),
    "six": Decimal(6),
    "seven": Decimal(7),
    "eight": Decimal(8),
    "nine": Decimal(9),
    "ten": Decimal(10),
    "twenty": Decimal(20),
    "thirty": Decimal(30),
    "forty": Decimal(40),
    "fifty": Decimal(50),
    "sixty": Decimal(60),
    "seventy": Decimal(70),
    "eighty": Decimal(80),
    "ninety": Decimal(90),
}
TENURE_WORDS = {
    "six": 6,
    "twelve": 12,
    "eighteen": 18,
    "twenty four": 24,
    "twenty-four": 24,
}


def _calculation_overrides(question: str) -> tuple[Decimal | None, int | None]:
    """Extract only explicit, bounded hypothetical inputs from a question."""

    lowered = question.casefold().replace(",", "")
    amount: Decimal | None = None
    amount_match = re.search(
        r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)\s+"
        r"(lakh|lac|thousand)\b",
        lowered,
    )
    if amount_match:
        raw = amount_match.group(1)
        base = Decimal(raw) if raw[0].isdigit() else NUMBER_WORDS[raw]
        scale = (
            Decimal(100000)
            if amount_match.group(2) in {"lakh", "lac"}
            else Decimal(1000)
        )
        amount = base * scale

    tenure: int | None = None
    tenure_match = re.search(
        r"\b(6|12|18|24|six|twelve|eighteen|twenty[ -]four)\s+months?\b",
        lowered,
    )
    if tenure_match:
        raw_tenure = tenure_match.group(1)
        tenure = int(raw_tenure) if raw_tenure.isdigit() else TENURE_WORDS[raw_tenure]
    return amount, tenure


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

    def _calculation_answer(
        self, question: str, draft: ApplicationDraft
    ) -> GroundedAnswer:
        amount_override, tenure_override = _calculation_overrides(question)
        try:
            projection = self.calculator.calculate_hypothetical(
                draft,
                requested_amount=amount_override,
                tenure_months=tenure_override,
            )
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
        comparison = None
        if (amount_override is not None or tenure_override is not None) and (
            "change" in lowered or "compare" in lowered
        ):
            try:
                baseline = self.calculator.calculate(draft)
                if (
                    baseline.requested_amount != projection.requested_amount
                    or baseline.tenure_months != projection.tenure_months
                ):
                    comparison = baseline
            except ProjectionUnavailable:
                pass

        if comparison is not None and "total interest" in lowered:
            emi_delta = projection.emi - comparison.emi
            interest_delta = projection.total_interest - comparison.total_interest
            emi_direction = "increases" if emi_delta >= 0 else "decreases"
            interest_direction = "increases" if interest_delta >= 0 else "decreases"
            text = (
                f"At {projection.tenure_months} months, the calculated monthly EMI would be "
                f"Rs. {projection.emi}, and total interest would be Rs. {projection.total_interest}. "
                f"Compared with the current {comparison.tenure_months}-month projection, EMI "
                f"{emi_direction} by Rs. {abs(emi_delta)}, and total interest "
                f"{interest_direction} by Rs. {abs(interest_delta)}. "
                "This comparison does not change the draft."
            )
            labelled_values = {
                "emi": str(projection.emi),
                "total_interest": str(projection.total_interest),
                "emi_change": str(abs(emi_delta)),
                "total_interest_change": str(abs(interest_delta)),
                "tenure_months": str(projection.tenure_months),
            }
        elif "total interest" in lowered or "total repayment" in lowered:
            text = (
                f"At {projection.tenure_months} months, the calculated monthly EMI is "
                f"Rs. {projection.emi}, total interest is Rs. {projection.total_interest}, "
                f"and total repayment is Rs. {projection.total_repayment}."
            )
            labelled_values = {
                "emi": str(projection.emi),
                "total_interest": str(projection.total_interest),
                "total_repayment": str(projection.total_repayment),
                "tenure_months": str(projection.tenure_months),
            }
        elif (
            "receive" in lowered
            or "get" in lowered
            or "disburs" in lowered
            or "account" in lowered
        ):
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
