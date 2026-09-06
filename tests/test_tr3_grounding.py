from saarthi.config import REPOSITORY_ROOT
from saarthi.domain.contracts import CommittedFieldValue
from saarthi.domain.enums import ChangeKind, FieldId, SupportStatus, TurnRoute
from saarthi.providers.knowledge import LocalKnowledgeProvider, load_product_facts
from saarthi.services.calculator import FinancialCalculator
from saarthi.services.grounding import GroundedAnswerService


def service() -> GroundedAnswerService:
    facts = load_product_facts(
        REPOSITORY_ROOT / "data" / "product" / "saarthi_product_facts_v1.json"
    )
    return GroundedAnswerService(
        LocalKnowledgeProvider(facts),
        calculator=FinancialCalculator.from_product_facts(facts),
    )


async def test_supported_fee_question_returns_approved_fact_id(application):
    answer = await service().answer(
        "Is the processing fee included in EMI?",
        route=TurnRoute.PRODUCT_QUESTION,
        draft=application,
    )
    assert answer.support_status is SupportStatus.SUPPORTED
    assert answer.supporting_fact_ids
    assert all(
        identifier.startswith("SPL-") for identifier in answer.supporting_fact_ids
    )


async def test_unanswerable_question_abstains(application):
    answer = await service().answer(
        "Which branch manager will call me on Tuesday?",
        route=TurnRoute.PRODUCT_QUESTION,
        draft=application,
    )
    assert answer.support_status is SupportStatus.UNSUPPORTED
    assert answer.claims == []


async def test_calculation_requires_confirmed_amount_and_tenure(application):
    answer = await service().answer(
        "What is my EMI?", route=TurnRoute.CALCULATION, draft=application
    )
    assert answer.support_status is SupportStatus.UNSUPPORTED
    assert answer.abstention_reason


async def test_calculation_is_linked_and_labelled(application):
    application.revision = 2
    application.fields = {
        FieldId.REQUESTED_AMOUNT: CommittedFieldValue(
            field_id=FieldId.REQUESTED_AMOUNT,
            typed_value="100000.00",
            source_turn_id="t1",
            source_span="one lakh",
            normalizer_version="v1",
            validator_version="v1",
            committed_at_revision=1,
            last_change_kind=ChangeKind.INITIAL,
        ),
        FieldId.PREFERRED_TENURE: CommittedFieldValue(
            field_id=FieldId.PREFERRED_TENURE,
            typed_value=12,
            source_turn_id="t2",
            source_span="12 months",
            normalizer_version="v1",
            validator_version="v1",
            committed_at_revision=2,
            last_change_kind=ChangeKind.INITIAL,
        ),
    }
    answer = await service().answer(
        "What is my EMI?", route=TurnRoute.CALCULATION, draft=application
    )
    assert answer.support_status is SupportStatus.SUPPORTED
    assert answer.calculation_ids
    assert set(answer.labelled_values) == {"emi", "tenure_months"}
