from __future__ import annotations

import re
from decimal import Decimal

from num2words import num2words

from saarthi.domain.contracts import FinancialProjection, ResponsePlan, SpeechSegment

MARKDOWN_RE = re.compile(r"[*_#`>|]+")


def _rupees_for_ear(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"))
    rupees = int(rounded)
    paise = int((rounded - Decimal(rupees)) * 100)
    words = f"{num2words(rupees, lang='en_IN')} rupees"
    if paise:
        words += f" and {num2words(paise, lang='en_IN')} paise"
    return words


def _clean_for_speech(text: str) -> str:
    text = MARKDOWN_RE.sub("", text)
    text = text.replace("%", " percent ").replace("₹", " rupees ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ListenerRenderer:
    """TR-4 renderer. It formats approved plans; it never invents financial values."""

    def render(self, plan: ResponsePlan, *, generation_id: int) -> list[SpeechSegment]:
        if not plan.releasable:
            return []
        return [
            SpeechSegment(
                response_id=plan.response_id,
                order=index,
                generation_id=generation_id,
                text=_clean_for_speech(text),
                value_labels=dict(plan.labelled_values),
            )
            for index, text in enumerate(plan.message_segments)
            if text.strip()
        ]

    def projection_plan(self, projection: FinancialProjection) -> ResponsePlan:
        values = {
            "requested_amount": str(projection.requested_amount),
            "annual_interest_rate_percent": str(
                projection.annual_interest_rate_percent
            ),
            "tenure_months": str(projection.tenure_months),
            "processing_fee": str(projection.processing_fee),
            "tax_on_processing_fee": str(projection.tax_on_processing_fee),
            "net_disbursal": str(projection.net_disbursal),
            "emi": str(projection.emi),
            "total_repayment": str(projection.total_repayment),
        }
        segments = [
            f"Requested amount: {_rupees_for_ear(projection.requested_amount)}.",
            f"Tenure: {num2words(projection.tenure_months)} months.",
            f"Interest rate: {projection.annual_interest_rate_percent} percent per year, on a reducing balance.",
            f"Estimated monthly EMI: {_rupees_for_ear(projection.emi)}.",
            f"Processing fee: {_rupees_for_ear(projection.processing_fee)}.",
            f"Tax on the processing fee: {_rupees_for_ear(projection.tax_on_processing_fee)}.",
            f"Estimated net amount after those deductions: {_rupees_for_ear(projection.net_disbursal)}.",
            f"Estimated total of all instalments: {_rupees_for_ear(projection.total_repayment)}.",
            "This is a synthetic draft for review. It has not been submitted or approved.",
        ]
        return ResponsePlan(
            purpose="financial_summary",
            message_segments=segments,
            labelled_values=values,
            required_disclosures=[
                "synthetic",
                "draft_only",
                "not_submitted",
                "not_approved",
            ],
            release_gates=[],
        )

    @staticmethod
    def written_projection(projection: FinancialProjection) -> dict[str, str | int]:
        return {
            "label": "Draft for review - not submitted",
            "requested_amount": str(projection.requested_amount),
            "annual_interest_rate_percent": str(
                projection.annual_interest_rate_percent
            ),
            "tenure_months": projection.tenure_months,
            "processing_fee": str(projection.processing_fee),
            "tax_on_processing_fee": str(projection.tax_on_processing_fee),
            "total_deduction": str(projection.total_deduction),
            "net_disbursal": str(projection.net_disbursal),
            "emi": str(projection.emi),
            "total_repayment": str(projection.total_repayment),
            "total_interest": str(projection.total_interest),
            "projection_id": projection.projection_id,
            "source_application_revision": projection.source_application_revision,
        }

    @staticmethod
    def verify_projection_labels(
        plan: ResponsePlan, projection: FinancialProjection
    ) -> bool:
        expected = ListenerRenderer.written_projection(projection)
        comparable = {
            key: str(value)
            for key, value in expected.items()
            if key in plan.labelled_values
        }
        return bool(comparable) and all(
            plan.labelled_values[key] == value for key, value in comparable.items()
        )
