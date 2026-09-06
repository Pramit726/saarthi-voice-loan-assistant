from saarthi.domain.contracts import ApplicationPatch
from saarthi.domain.enums import FieldId
from saarthi.domain.reducer import GuardedReducer
from saarthi.storage.repository import InMemoryStateRepository


async def test_duplicate_patch_returns_recorded_result_without_second_mutation(
    application, conversation
):
    repository = InMemoryStateRepository()
    await repository.create(application, conversation)
    patch = ApplicationPatch(
        idempotency_key="same-key",
        session_id=conversation.session_id,
        application_id=application.application_id,
        expected_application_revision=0,
        source_turn_id="turn-1",
        source_generation_id=1,
        target_field=FieldId.REQUESTED_AMOUNT,
        normalized_candidate=100000,
        source_span="one lakh",
        explicit_target=True,
    )
    first = await repository.commit_patch(
        patch, current_generation_id=1, reducer=GuardedReducer()
    )
    second = await repository.commit_patch(
        patch, current_generation_id=1, reducer=GuardedReducer()
    )
    stored = await repository.get_draft(application.application_id)
    assert first.model_dump() == second.model_dump()
    assert stored.revision == 1
    assert len(stored.change_history) == 1
