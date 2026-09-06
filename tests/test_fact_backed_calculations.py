from copy import deepcopy
from decimal import Decimal

from saarthi.config import REPOSITORY_ROOT
from saarthi.domain.contracts import CommittedFieldValue
from saarthi.domain.enums import ChangeKind, FieldId, SupportStatus, TurnRoute
from saarthi.providers.knowledge import LocalKnowledgeProvider, load_product_facts
from saarthi.services.calculator import FinancialCalculator
from saarthi.services.grounding import GroundedAnswerService


def _facts():
    return load_product_facts(
        REPOSITORY_ROOT / "data" / "product" / "saarthi_product_facts_v1.json"
    )


def _field(field_id: FieldId, value, revision: int) -> CommittedFieldValue:
    return CommittedFieldValue(
        field_id=field_id,
        typed_value=value,
        source_turn_id=f"turn-{revision}",
        source_span=str(value),
        normalizer_version="test",
        validator_version="test",
        committed_at_revision=revision,
        last_change_kind=ChangeKind.INITIAL,
    )


def _service(facts) -> GroundedAnswerService:
    return GroundedAnswerService(
        LocalKnowledgeProvider(facts),
        calculator=FinancialCalculator.from_product_facts(facts),
    )


def test_calculator_parameters_come_from_approved_product_facts(application):
    facts = _facts()
    application.revision = 2
    application.fields = {
        FieldId.REQUESTED_AMOUNT: _field(FieldId.REQUESTED_AMOUNT, 100000, 1),
        FieldId.PREFERRED_TENURE: _field(FieldId.PREFERRED_TENURE, 12, 2),
    }
    standard = FinancialCalculator.from_product_facts(facts).calculate(application)

    changed = deepcopy(facts)
    rate_fact = next(fact for fact in changed if fact.topic == "interest_rate")
    rate_fact.numeric_values["annual_rate_percent"] = Decimal("20.00")
    higher_rate = FinancialCalculator.from_product_facts(changed).calculate(application)

    assert standard.annual_interest_rate_percent == Decimal("12.50")
    assert standard.processing_fee == Decimal("2000.00")
    assert higher_rate.annual_interest_rate_percent == Decimal("20.00")
    assert higher_rate.emi > standard.emi


async def test_hypothetical_tenure_uses_confirmed_amount_without_mutation(
    application,
):
    facts = _facts()
    application.revision = 1
    application.fields = {
        FieldId.REQUESTED_AMOUNT: _field(FieldId.REQUESTED_AMOUNT, 100000, 1)
    }
    before = application.model_dump(mode="json")

    answer = await _service(facts).answer(
        "If I choose twelve months, what would the EMI be?",
        route=TurnRoute.CALCULATION,
        draft=application,
    )

    assert answer.support_status is SupportStatus.SUPPORTED
    assert answer.labelled_values["tenure_months"] == "12"
    assert answer.calculation_ids
    assert application.model_dump(mode="json") == before


async def test_hypothetical_comparison_reports_effect_and_preserves_draft(
    application,
):
    facts = _facts()
    application.revision = 2
    application.fields = {
        FieldId.REQUESTED_AMOUNT: _field(FieldId.REQUESTED_AMOUNT, 80000, 1),
        FieldId.PREFERRED_TENURE: _field(FieldId.PREFERRED_TENURE, 12, 2),
    }
    before = application.model_dump(mode="json")

    answer = await _service(facts).answer(
        "If I change tenure to six months, how will the EMI and total interest change?",
        route=TurnRoute.CALCULATION,
        draft=application,
    )

    spoken = " ".join(claim.text for claim in answer.claims)
    assert answer.support_status is SupportStatus.SUPPORTED
    assert answer.labelled_values["tenure_months"] == "6"
    assert "does not change the draft" in spoken
    assert "Compared with the current 12-month projection" in spoken
    assert application.model_dump(mode="json") == before
