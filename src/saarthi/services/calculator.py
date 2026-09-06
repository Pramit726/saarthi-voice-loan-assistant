from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext

from saarthi.domain.contracts import ApplicationDraft, FinancialProjection
from saarthi.domain.enums import FieldId

getcontext().prec = 28
PAISE = Decimal("0.01")


class ProjectionUnavailable(ValueError):
    pass


class FinancialCalculator:
    version = "reducing-balance-v1"
    annual_rate_percent = Decimal("12.50")
    processing_fee_percent = Decimal("2.00")
    tax_percent = Decimal("18.00")
    fact_set_version = "1.1"

    def calculate(self, draft: ApplicationDraft) -> FinancialProjection:
        amount_record = draft.fields.get(FieldId.REQUESTED_AMOUNT)
        tenure_record = draft.fields.get(FieldId.PREFERRED_TENURE)
        if not amount_record or not tenure_record:
            raise ProjectionUnavailable(
                "Requested amount and preferred tenure must be confirmed first."
            )

        principal = Decimal(str(amount_record.typed_value))
        tenure = int(tenure_record.typed_value)
        monthly_rate = self.annual_rate_percent / Decimal(1200)
        growth = (Decimal(1) + monthly_rate) ** tenure
        emi = principal * monthly_rate * growth / (growth - Decimal(1))
        processing_fee = principal * self.processing_fee_percent / Decimal(100)
        tax = processing_fee * self.tax_percent / Decimal(100)
        total_deduction = processing_fee + tax
        net_disbursal = principal - total_deduction
        total_repayment = emi * tenure

        money = lambda value: value.quantize(PAISE, rounding=ROUND_HALF_UP)
        return FinancialProjection(
            source_application_revision=draft.revision,
            product_id=draft.product_id,
            product_version=draft.product_version,
            fact_set_version=self.fact_set_version,
            calculator_version=self.version,
            requested_amount=money(principal),
            annual_interest_rate_percent=self.annual_rate_percent,
            tenure_months=tenure,
            processing_fee=money(processing_fee),
            tax_on_processing_fee=money(tax),
            total_deduction=money(total_deduction),
            net_disbursal=money(net_disbursal),
            emi=money(emi),
            total_repayment=money(total_repayment),
            total_interest=money(total_repayment - principal),
        )
