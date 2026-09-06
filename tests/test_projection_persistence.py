from saarthi.domain.contracts import CommittedFieldValue
from saarthi.domain.enums import ChangeKind, FieldId
from saarthi.services.calculator import FinancialCalculator
from saarthi.storage.repository import InMemoryStateRepository


async def test_projection_can_attach_only_to_its_source_revision(
    application, conversation
):
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
            source_span="twelve months",
            normalizer_version="v1",
            validator_version="v1",
            committed_at_revision=2,
            last_change_kind=ChangeKind.INITIAL,
        ),
    }
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    projection = FinancialCalculator().calculate(application)
    stored = await repository.attach_projection(
        application.application_id, 2, projection
    )
    assert stored.current_projection.projection_id == projection.projection_id

    stale = projection.model_copy(update={"source_application_revision": 1})
    import pytest

    with pytest.raises(ValueError, match="stale_projection"):
        await repository.attach_projection(application.application_id, 2, stale)
