import pytest

from saarthi.domain.contracts import ActiveJob, SpeechSegment, TurnProposal
from saarthi.domain.enums import (
    ControlCommand,
    DeliveryStatus,
    FieldId,
    JobKind,
    TurnAct,
    TurnRoute,
)
from saarthi.domain.state import ConversationStateMachine, StaleWorkError


def doubt_proposal() -> TurnProposal:
    return TurnProposal(
        source_transcript_id="t1",
        acts=[TurnAct.DOUBT],
        route=TurnRoute.PRODUCT_QUESTION,
        uncertainty=0,
        rationale_code="product_doubt",
    )


def test_doubt_saves_and_restores_exact_pending_field(conversation):
    machine = ConversationStateMachine()
    state = machine.accept_proposal(conversation, doubt_proposal())
    assert state.resume_checkpoint.pending_field is FieldId.REQUESTED_AMOUNT
    restored = machine.restore_checkpoint(state, 0)
    assert restored.pending_field is FieldId.REQUESTED_AMOUNT
    assert restored.resume_checkpoint is None


def test_repeat_invalidates_audio_but_not_application_revision(conversation):
    machine = ConversationStateMachine()
    conversation.linked_application_revision = 4
    conversation.output_queue = [
        SpeechSegment(response_id="r", order=0, generation_id=0, text="hello")
    ]
    updated = machine.apply_control(conversation, ControlCommand.REPEAT)
    assert updated.generation_id == 1
    assert updated.linked_application_revision == 4
    assert updated.output_queue == []


def test_stale_job_is_detected(conversation):
    machine = ConversationStateMachine()
    job = ActiveJob(
        kind=JobKind.RETRIEVAL,
        turn_id="turn-1",
        route=TurnRoute.PRODUCT_QUESTION,
        captured_state_version=0,
        captured_generation_id=0,
        captured_application_revision=0,
    )
    newer = machine.begin_final_turn(conversation, "turn-2")
    with pytest.raises(StaleWorkError):
        machine.ensure_current(newer, job)


def test_only_fully_delivered_segment_enters_heard_history(conversation):
    machine = ConversationStateMachine()
    conversation.output_queue = [
        SpeechSegment(response_id="r", segment_id="s1", order=0, generation_id=0, text="fully heard"),
        SpeechSegment(response_id="r", segment_id="s2", order=1, generation_id=0, text="not heard"),
    ]
    updated = machine.mark_segment_delivered(conversation, "s1")
    assert updated.last_fully_heard_response[0].segment_id == "s1"
    assert updated.output_queue[1].delivery_status is DeliveryStatus.PLANNED
