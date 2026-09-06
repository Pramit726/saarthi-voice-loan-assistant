from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext

from saarthi.domain.contracts import ApplicationDraft, FinancialProjection, ProductFact
from saarthi.domain.enums import FieldId

getcontext().prec = 28
PAISE = Decimal("0.01")


class ProjectionUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class ProductTerms:
    """Approved numeric inputs used by the deterministic calculator."""

    product_id: str
    product_version: str
    fact_set_version: str
    annual_rate_percent: Decimal
    processing_fee_percent: Decimal
    tax_percent: Decimal

    @classmethod
    def from_facts(
        cls,
        facts: list[ProductFact],
        *,
        product_id: str,
        product_version: str,
    ) -> ProductTerms:
        scoped = {
            fact.topic: fact
            for fact in facts
            if fact.status == "approved"
            and fact.product_id == product_id
            and fact.product_version == product_version
        }

        def required(topic: str, key: str) -> Decimal:
            fact = scoped.get(topic)
            if fact is None or key not in fact.numeric_values:
                raise ValueError(f"missing_approved_calculator_fact:{topic}:{key}")
            return Decimal(str(fact.numeric_values[key]))

        rate = scoped.get("interest_rate")
        fee = scoped.get("processing_fee")
        tax = scoped.get("processing_fee_tax")
        fact_versions = {
            fact.fact_set_version for fact in (rate, fee, tax) if fact is not None
        }
        if len(fact_versions) != 1:
            raise ValueError("calculator_fact_set_version_mismatch")

        return cls(
            product_id=product_id,
            product_version=product_version,
            fact_set_version=fact_versions.pop(),
            annual_rate_percent=required("interest_rate", "annual_rate_percent"),
            processing_fee_percent=required("processing_fee", "processing_fee_percent"),
            tax_percent=required("processing_fee_tax", "tax_percent_of_fee"),
        )


class FinancialCalculator:
    version = "reducing-balance-v2-fact-backed"

    def __init__(self, terms: ProductTerms) -> None:
        self.terms = terms

    @classmethod
    def from_product_facts(
        cls,
        facts: list[ProductFact],
        *,
        product_id: str = "SPL-DEMO-01",
        product_version: str = "1.1",
    ) -> FinancialCalculator:
        return cls(
            ProductTerms.from_facts(
                facts,
                product_id=product_id,
                product_version=product_version,
            )
        )

    def calculate(self, draft: ApplicationDraft) -> FinancialProjection:
        amount_record = draft.fields.get(FieldId.REQUESTED_AMOUNT)
        tenure_record = draft.fields.get(FieldId.PREFERRED_TENURE)
        if not amount_record or not tenure_record:
            raise ProjectionUnavailable(
                "Requested amount and preferred tenure must be confirmed first."
            )

        return self._calculate_values(
            draft,
            principal=Decimal(str(amount_record.typed_value)),
            tenure=int(tenure_record.typed_value),
        )

    def calculate_hypothetical(
        self,
        draft: ApplicationDraft,
        *,
        requested_amount: Decimal | None = None,
        tenure_months: int | None = None,
    ) -> FinancialProjection:
        """Calculate without mutating or attaching values to the draft."""

        amount_record = draft.fields.get(FieldId.REQUESTED_AMOUNT)
        tenure_record = draft.fields.get(FieldId.PREFERRED_TENURE)
        principal = (
            requested_amount
            if requested_amount is not None
            else Decimal(str(amount_record.typed_value))
            if amount_record is not None
            else None
        )
        tenure = (
            tenure_months
            if tenure_months is not None
            else int(tenure_record.typed_value)
            if tenure_record is not None
            else None
        )
        if principal is None or tenure is None:
            raise ProjectionUnavailable(
                "A confirmed or explicitly hypothetical amount and tenure are required."
            )
        return self._calculate_values(draft, principal=principal, tenure=tenure)

    def _calculate_values(
        self,
        draft: ApplicationDraft,
        *,
        principal: Decimal,
        tenure: int,
    ) -> FinancialProjection:
        if (
            draft.product_id != self.terms.product_id
            or draft.product_version != self.terms.product_version
        ):
            raise ProjectionUnavailable(
                "No approved calculator terms match this product version."
            )
        monthly_rate = self.terms.annual_rate_percent / Decimal(1200)
        growth = (Decimal(1) + monthly_rate) ** tenure
        emi = (
            principal / tenure
            if monthly_rate == 0
            else principal * monthly_rate * growth / (growth - Decimal(1))
        )
        processing_fee = principal * self.terms.processing_fee_percent / Decimal(100)
        tax = processing_fee * self.terms.tax_percent / Decimal(100)
        total_deduction = processing_fee + tax
        net_disbursal = principal - total_deduction
        total_repayment = emi * tenure

        money = lambda value: value.quantize(PAISE, rounding=ROUND_HALF_UP)
        return FinancialProjection(
            source_application_revision=draft.revision,
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=self.terms.fact_set_version,
            calculator_version=self.version,
            requested_amount=money(principal),
            annual_interest_rate_percent=self.terms.annual_rate_percent,
            tenure_months=tenure,
            processing_fee=money(processing_fee),
            tax_on_processing_fee=money(tax),
            total_deduction=money(total_deduction),
            net_disbursal=money(net_disbursal),
            emi=money(emi),
            total_repayment=money(total_repayment),
            total_interest=money(total_repayment - principal),
        )
