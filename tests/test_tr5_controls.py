from saarthi.domain.contracts import ActiveJob, SpeechSegment
from saarthi.domain.enums import (
    ControlCommand,
    DeliveryStatus,
    JobKind,
    JobStatus,
    SessionStatus,
    TurnRoute,
)
from saarthi.domain.state import ConversationStateMachine


def test_stop_cancels_active_work_and_queued_audio(conversation):
    conversation.active_jobs["job"] = ActiveJob(
        job_id="job",
        kind=JobKind.TTS,
        turn_id="turn-1",
        route=TurnRoute.PRODUCT_QUESTION,
        captured_state_version=0,
        captured_generation_id=0,
        captured_application_revision=0,
    )
    conversation.output_queue = [
        SpeechSegment(response_id="r", order=0, generation_id=0, text="obsolete speech")
    ]
    stopped = ConversationStateMachine().apply_control(
        conversation, ControlCommand.STOP
    )
    assert stopped.generation_id == 1
    assert stopped.active_jobs["job"].status is JobStatus.CANCELLED
    assert stopped.output_queue == []
    assert stopped.status is SessionStatus.ACTIVE


def test_pause_preserves_pending_field_and_revision(conversation):
    conversation.linked_application_revision = 3
    paused = ConversationStateMachine().apply_control(
        conversation, ControlCommand.PAUSE
    )
    assert paused.resume_checkpoint.pending_field == conversation.pending_field
    assert paused.linked_application_revision == 3


def test_repeat_does_not_replay_unheard_segment(conversation):
    conversation.output_queue = [
        SpeechSegment(
            response_id="r",
            order=0,
            generation_id=0,
            text="unheard",
            delivery_status=DeliveryStatus.INTERRUPTED,
        )
    ]
    repeated = ConversationStateMachine().apply_control(
        conversation, ControlCommand.REPEAT
    )
    assert repeated.last_fully_heard_response == []


def test_go_back_changes_navigation_not_application_revision(conversation):
    from saarthi.domain.enums import FieldId

    conversation.pending_field = FieldId.PREFERRED_TENURE
    conversation.linked_application_revision = 2
    changed = ConversationStateMachine().apply_control(
        conversation, ControlCommand.GO_BACK
    )
    assert changed.pending_field is FieldId.LOAN_PURPOSE
    assert changed.linked_application_revision == 2
