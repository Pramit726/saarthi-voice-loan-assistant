from __future__ import annotations

from copy import deepcopy

from .contracts import (
    ActiveJob,
    ConversationState,
    ResumeCheckpoint,
    TurnProposal,
    utc_now,
)
from .enums import (
    ControlCommand,
    ConversationPhase,
    DeliveryStatus,
    FieldId,
    JobStatus,
    SessionStatus,
    TurnRoute,
)
from .fields import FIELD_DEFINITIONS, FIELD_ORDER, next_unanswered_field


class StaleWorkError(RuntimeError):
    pass


class ConversationStateMachine:
    """Owns workflow position and generation fences, never application values."""

    def begin_final_turn(
        self, state: ConversationState, turn_id: str
    ) -> ConversationState:
        updated = deepcopy(state)
        updated.current_turn_id = turn_id
        updated.current_proposal = None
        updated.state_version += 1
        updated.generation_id += 1
        self._cancel_old_jobs(updated)
        self._cancel_output(updated)
        updated.updated_at = utc_now()
        return updated

    def accept_proposal(
        self, state: ConversationState, proposal: TurnProposal
    ) -> ConversationState:
        updated = deepcopy(state)
        updated.current_proposal = proposal
        if proposal.route in {
            TurnRoute.FIELD_DOUBT,
            TurnRoute.PRODUCT_QUESTION,
            TurnRoute.CALCULATION,
        }:
            self._save_resume_checkpoint(updated)
            updated.phase = ConversationPhase.EXPLANATION
        elif proposal.route is TurnRoute.CORRECTION:
            self._save_resume_checkpoint(updated)
            updated.phase = ConversationPhase.CORRECTION
        elif proposal.route is TurnRoute.CLARIFICATION:
            updated.phase = ConversationPhase.CLARIFICATION
        elif proposal.route is TurnRoute.FIELD_ANSWER:
            updated.phase = ConversationPhase.COLLECTION
        updated.state_version += 1
        updated.updated_at = utc_now()
        return updated

    def after_commit(
        self, state: ConversationState, committed_fields: set[FieldId], revision: int
    ) -> ConversationState:
        updated = deepcopy(state)
        updated.linked_application_revision = revision
        updated.pending_field = next_unanswered_field(
            {field_id: True for field_id in committed_fields}
        )
        updated.phase = (
            ConversationPhase.REVIEW
            if updated.pending_field is None
            else ConversationPhase.COLLECTION
        )
        updated.resume_checkpoint = None
        updated.pending_write_confirmation = None
        updated.state_version += 1
        updated.last_safe_prompt = (
            "Your draft is ready for review."
            if updated.pending_field is None
            else FIELD_DEFINITIONS[updated.pending_field].prompt
        )
        updated.updated_at = utc_now()
        return updated

    @staticmethod
    def hold_for_confirmation(
        state: ConversationState, proposal: TurnProposal
    ) -> ConversationState:
        updated = deepcopy(state)
        updated.pending_write_confirmation = proposal
        updated.phase = ConversationPhase.CLARIFICATION
        updated.state_version += 1
        updated.updated_at = utc_now()
        return updated

    @staticmethod
    def discard_pending_write(state: ConversationState) -> ConversationState:
        updated = deepcopy(state)
        updated.pending_write_confirmation = None
        updated.phase = ConversationPhase.COLLECTION
        updated.state_version += 1
        updated.updated_at = utc_now()
        return updated

    def restore_checkpoint(
        self, state: ConversationState, current_application_revision: int
    ) -> ConversationState:
        updated = deepcopy(state)
        checkpoint = updated.resume_checkpoint
        if checkpoint is None:
            return updated
        updated.pending_field = checkpoint.pending_field
        updated.navigation_stack = list(checkpoint.navigation_stack)
        updated.linked_application_revision = current_application_revision
        updated.phase = ConversationPhase.COLLECTION
        updated.last_safe_prompt = checkpoint.resume_prompt
        updated.resume_checkpoint = None
        updated.state_version += 1
        updated.updated_at = utc_now()
        return updated

    def apply_control(
        self, state: ConversationState, command: ControlCommand
    ) -> ConversationState:
        updated = deepcopy(state)
        updated.generation_id += 1
        self._cancel_old_jobs(updated)
        self._cancel_output(updated)

        if command in {ControlCommand.STOP, ControlCommand.CANCEL}:
            updated.status = SessionStatus.CANCELLED
            updated.phase = ConversationPhase.STOPPED
        elif command is ControlCommand.PAUSE:
            self._save_resume_checkpoint(updated)
            updated.status = SessionStatus.PAUSED
        elif command is ControlCommand.RESUME:
            updated.status = SessionStatus.ACTIVE
            updated = self.restore_checkpoint(
                updated, updated.linked_application_revision
            )
        elif command is ControlCommand.GO_BACK:
            current_index = (
                FIELD_ORDER.index(updated.pending_field)
                if updated.pending_field in FIELD_ORDER
                else len(FIELD_ORDER)
            )
            if current_index > 0:
                updated.pending_field = FIELD_ORDER[current_index - 1]
                updated.phase = ConversationPhase.COLLECTION
        elif command is ControlCommand.SHOW_SUMMARY:
            updated.phase = ConversationPhase.REVIEW
        # Repeat deliberately keeps the same workflow position.

        updated.state_version += 1
        updated.updated_at = utc_now()
        return updated

    @staticmethod
    def register_job(state: ConversationState, job: ActiveJob) -> ConversationState:
        updated = deepcopy(state)
        updated.active_jobs[job.job_id] = job
        updated.updated_at = utc_now()
        return updated

    @staticmethod
    def ensure_current(state: ConversationState, job: ActiveJob) -> None:
        if (
            job.captured_state_version != state.state_version
            or job.captured_generation_id != state.generation_id
            or job.captured_application_revision != state.linked_application_revision
        ):
            raise StaleWorkError(job.job_id)

    @staticmethod
    def mark_segment_delivered(
        state: ConversationState, segment_id: str
    ) -> ConversationState:
        updated = deepcopy(state)
        for segment in updated.output_queue:
            if segment.segment_id == segment_id:
                segment.delivery_status = DeliveryStatus.DELIVERED
                segment.heard_character_count = len(segment.text)
        delivered = [
            item
            for item in updated.output_queue
            if item.delivery_status is DeliveryStatus.DELIVERED
        ]
        if delivered:
            updated.last_fully_heard_response = delivered
        updated.updated_at = utc_now()
        return updated

    @staticmethod
    def _save_resume_checkpoint(state: ConversationState) -> None:
        if state.resume_checkpoint is not None:
            return
        prompt = state.last_safe_prompt
        if not prompt and state.pending_field:
            prompt = FIELD_DEFINITIONS[state.pending_field].prompt
        state.resume_checkpoint = ResumeCheckpoint(
            pending_field=state.pending_field,
            application_revision=state.linked_application_revision,
            state_version=state.state_version,
            resume_prompt=prompt or "Let us continue your draft.",
            navigation_stack=list(state.navigation_stack),
            last_heard_segment_id=(
                state.last_fully_heard_response[-1].segment_id
                if state.last_fully_heard_response
                else None
            ),
        )

    @staticmethod
    def _cancel_old_jobs(state: ConversationState) -> None:
        for job in state.active_jobs.values():
            if job.status is JobStatus.ACTIVE:
                job.status = JobStatus.CANCELLED

    @staticmethod
    def _cancel_output(state: ConversationState) -> None:
        for segment in state.output_queue:
            if segment.delivery_status not in {
                DeliveryStatus.DELIVERED,
                DeliveryStatus.CANCELLED,
            }:
                segment.delivery_status = DeliveryStatus.CANCELLED
        state.output_queue = []
