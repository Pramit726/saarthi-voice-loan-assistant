import pytest

from saarthi.domain.contracts import ApplicationDraft, ApplicationPatch, ConversationState
from saarthi.domain.enums import FieldId
from saarthi.domain.reducer import GuardedReducer
from saarthi.storage.repository import InMemoryStateRepository


async def test_overlapping_turn_numbers_do_not_cross_sessions():
    repository = InMemoryStateRepository()
    draft_a = ApplicationDraft(application_id="app-a", owner_session_id="session-a")
    state_a = ConversationState(session_id="session-a", application_id="app-a", participant_id="user-a")
    draft_b = ApplicationDraft(application_id="app-b", owner_session_id="session-b")
    state_b = ConversationState(session_id="session-b", application_id="app-b", participant_id="user-b")
    await repository.create(draft_a, state_a)
    await repository.create(draft_b, state_b)
    wrong_session_patch = ApplicationPatch(
        idempotency_key="session-b:turn-1",
        session_id="session-b",
        application_id="app-a",
        expected_application_revision=0,
        source_turn_id="turn-1",
        source_generation_id=1,
        target_field=FieldId.REQUESTED_AMOUNT,
        normalized_candidate=100000,
        source_span="one lakh",
        explicit_target=True,
    )
    result = await repository.commit_patch(
        wrong_session_patch, current_generation_id=1, reducer=GuardedReducer()
    )
    assert not result.accepted
    assert result.reason_code == "session_mismatch"
    assert (await repository.get_draft("app-a")).revision == 0
    assert (await repository.get_draft("app-b")).revision == 0
