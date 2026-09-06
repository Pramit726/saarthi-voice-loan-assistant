from __future__ import annotations

from time import perf_counter

from saarthi.domain.contracts import (
    ApplicationPatch,
    ConversationState,
    FinalTranscript,
    ResponsePlan,
    TraceEvent,
    TurnOutcome,
)
from saarthi.domain.enums import (
    ChangeKind,
    ControlCommand,
    TurnAct,
    TurnRoute,
)
from saarthi.domain.reducer import GuardedReducer
from saarthi.domain.state import ConversationStateMachine
from saarthi.services.calculator import ProjectionUnavailable
from saarthi.services.grounding import GroundedAnswerService
from saarthi.services.interpreter import TurnInterpreter
from saarthi.services.planner import ResponsePlanner
from saarthi.services.renderer import ListenerRenderer
from saarthi.storage.repository import StateRepository


class SessionNotFound(KeyError):
    pass


class TurnOrchestrator:
    def __init__(
        self,
        *,
        repository: StateRepository,
        interpreter: TurnInterpreter,
        grounding: GroundedAnswerService,
        planner: ResponsePlanner,
        renderer: ListenerRenderer,
        reducer: GuardedReducer | None = None,
        state_machine: ConversationStateMachine | None = None,
    ) -> None:
        self.repository = repository
        self.interpreter = interpreter
        self.grounding = grounding
        self.planner = planner
        self.renderer = renderer
        self.reducer = reducer or GuardedReducer()
        self.state_machine = state_machine or ConversationStateMachine()

    async def process_final_transcript(
        self, transcript: FinalTranscript
    ) -> TurnOutcome:
        started = perf_counter()
        state = await self.repository.get_state(transcript.session_id)
        if state is None:
            raise SessionNotFound(transcript.session_id)
        draft = await self.repository.get_draft(state.application_id)
        if draft is None:
            raise SessionNotFound(state.application_id)

        if not transcript.is_final:
            plan = self.planner.safe_fallback("interim_transcript_ignored")
            return TurnOutcome(state=state, draft=draft, response_plan=plan)

        state = self.state_machine.begin_final_turn(state, transcript.turn_id)
        await self.repository.save_state(state)
        await self._trace(
            state,
            "final_transcript_accepted",
            "stt_gateway",
            "accepted",
            {
                "transcript_id": transcript.transcript_id,
                "confidence": transcript.confidence,
            },
        )

        try:
            proposal = await self.interpreter.interpret(transcript, state)
        except Exception as exc:  # noqa: BLE001 - all interpreter failures must fail closed
            state.failure_component = "interpreter"
            state.failure_reason = type(exc).__name__
            await self.repository.save_state(state)
            plan = self.planner.safe_fallback("provider_failure")
            segments = self.renderer.render(plan, generation_id=state.generation_id)
            return TurnOutcome(
                state=state, draft=draft, response_plan=plan, speech_segments=segments
            )

        state = self.state_machine.accept_proposal(state, proposal)
        await self.repository.save_state(state)
        await self._trace(
            state,
            "turn_interpreted",
            "tr1_interpreter",
            proposal.route.value,
            {
                "proposal_id": proposal.proposal_id,
                "acts": [act.value for act in proposal.acts],
                "target_field": proposal.target_field.value
                if proposal.target_field
                else None,
                "control": proposal.control.value if proposal.control else None,
                "explicit_write": proposal.explicit_write,
                "rationale_code": proposal.rationale_code,
            },
        )

        commit_result = None
        grounded_answer = None

        if proposal.route is TurnRoute.CONTROL and proposal.control:
            repeat_text = [segment.text for segment in state.last_fully_heard_response]
            state = self.state_machine.apply_control(state, proposal.control)
            if proposal.control is ControlCommand.CANCEL:
                draft = await self.repository.cancel_draft(
                    draft.application_id, state.session_id
                )
            await self.repository.save_state(state)
            if (
                proposal.control is ControlCommand.SHOW_SUMMARY
                and draft.current_projection
            ):
                plan = self.renderer.projection_plan(draft.current_projection)
                plan = self.planner.guard.evaluate(plan, financial_response=True)
            else:
                plan = self.planner.for_control(
                    proposal.control, repeat_text=repeat_text
                )

        elif proposal.rationale_code == "discard_pending_write":
            state = self.state_machine.discard_pending_write(state)
            state = self.state_machine.restore_checkpoint(state, draft.revision)
            await self.repository.save_state(state)
            prompt = state.last_safe_prompt or "Let us continue your draft."
            plan = ResponsePlan(
                purpose="discard_pending_write",
                message_segments=["Okay, I did not change the draft.", prompt],
            )
            plan = self.planner.guard.evaluate(plan)

        elif (
            proposal.rationale_code != "confirmed_pending_write"
            and proposal.explicit_write
            and proposal.target_field is not None
            and (
                proposal.route is TurnRoute.CORRECTION
                or proposal.target_field in draft.fields
            )
        ):
            # The stored draft is authoritative. Models occasionally label an
            # explicit update to an existing field as a normal field answer.
            # Treat it as a correction regardless of that route label so the
            # value cannot silently overwrite the committed draft.
            state = self.state_machine.hold_for_confirmation(state, proposal)
            await self.repository.save_state(state)
            current = (
                draft.fields.get(proposal.target_field)
                if proposal.target_field
                else None
            )
            current_text = str(current.typed_value) if current else "not answered"
            plan = ResponsePlan(
                purpose="confirm_correction",
                message_segments=[
                    f"The current {proposal.target_field.value.replace('_', ' ')} is {current_text}.",
                    f"Should I change it to {proposal.candidate_value}? Please say yes or no.",
                ],
            )
            plan = self.planner.guard.evaluate(plan)

        elif (
            proposal.route in {TurnRoute.FIELD_ANSWER, TurnRoute.CORRECTION}
            and proposal.explicit_write
        ):
            is_correction = (
                TurnAct.CORRECTION in proposal.acts
                or proposal.target_field in draft.fields
            )
            patch = ApplicationPatch(
                idempotency_key=f"{transcript.turn_id}:{proposal.proposal_id}",
                session_id=state.session_id,
                application_id=draft.application_id,
                expected_application_revision=draft.revision,
                source_turn_id=transcript.turn_id,
                source_generation_id=state.generation_id,
                target_field=proposal.target_field,
                normalized_candidate=proposal.candidate_value,
                source_span=proposal.source_span or transcript.text,
                explicit_target=True,
                confirmation_required=is_correction,
                confirmed=(proposal.rationale_code == "confirmed_pending_write"),
                change_kind=ChangeKind.CORRECTION
                if is_correction
                else ChangeKind.INITIAL,
            )
            commit_result = await self.repository.commit_patch(
                patch,
                current_generation_id=state.generation_id,
                reducer=self.reducer,
            )
            if commit_result.accepted and commit_result.draft:
                draft = commit_result.draft
                try:
                    projection = self.grounding.calculator.calculate(draft)
                    draft = await self.repository.attach_projection(
                        draft.application_id, draft.revision, projection
                    )
                except ProjectionUnavailable:
                    pass
                state = self.state_machine.after_commit(
                    state, set(draft.fields), draft.revision
                )
                await self.repository.save_state(state)
            plan = self.planner.for_commit(
                commit_result, next_field=state.pending_field
            )
            await self._trace(
                state,
                "application_patch_decided",
                "guarded_reducer",
                commit_result.reason_code,
                {
                    "accepted": commit_result.accepted,
                    "changed_field": commit_result.changed_field.value
                    if commit_result.changed_field
                    else None,
                    "previous_revision": commit_result.previous_revision,
                    "new_revision": commit_result.new_revision,
                    "new_value": commit_result.new_value,
                },
            )

        elif proposal.route in {
            TurnRoute.FIELD_DOUBT,
            TurnRoute.PRODUCT_QUESTION,
            TurnRoute.CALCULATION,
        }:
            if (
                proposal.candidate_value is not None
                and proposal.target_field is not None
            ):
                state = self.state_machine.hold_for_confirmation(state, proposal)
            grounded_answer = await self.grounding.answer(
                transcript.text,
                route=proposal.route,
                draft=draft,
            )
            resume = (
                "Should I record your proposed answer? Please say yes or no."
                if state.pending_write_confirmation
                else (
                    state.resume_checkpoint.resume_prompt
                    if state.resume_checkpoint
                    else None
                )
            )
            plan = self.planner.for_grounded_answer(
                grounded_answer, resume_prompt=resume
            )
            if not state.pending_write_confirmation:
                state = self.state_machine.restore_checkpoint(state, draft.revision)
            await self.repository.save_state(state)
            await self._trace(
                state,
                "grounding_decided",
                "tr3_answer_service",
                grounded_answer.support_status.value,
                {
                    "fact_ids": grounded_answer.supporting_fact_ids,
                    "calculation_ids": grounded_answer.calculation_ids,
                    "abstention_reason": grounded_answer.abstention_reason,
                },
            )

        elif (
            proposal.rationale_code in {"affirmation", "non_specific_confirmation"}
            and proposal.candidate_value is None
            and state.pending_field is not None
        ):
            # If the previous response was interrupted, users often say
            # "yes" or "okay" to indicate that they are ready to continue.
            # There is no pending write anymore, so do not send this through
            # the generic fallback. Re-ask the current field instead.
            prompt = state.last_safe_prompt or "Let us continue your draft."
            plan = ResponsePlan(
                purpose="resume_prompt",
                message_segments=[prompt],
                resume_instruction=prompt,
            )
            plan = self.planner.guard.evaluate(plan)

        else:
            if proposal.rationale_code == "discard_pending_write":
                state = self.state_machine.discard_pending_write(state)
            plan = self.planner.safe_fallback("clarification")

        if not plan.releasable:
            await self._trace(
                state,
                "response_blocked",
                "tr6_response_guard",
                "blocked",
                {
                    "failed_gates": [
                        gate.gate for gate in plan.release_gates if not gate.passed
                    ]
                },
            )
            plan = self.planner.safe_fallback("unsafe_response")

        segments = self.renderer.render(plan, generation_id=state.generation_id)
        state.output_queue = segments
        await self.repository.save_state(state)
        await self._trace(
            state,
            "response_released",
            "listener_renderer",
            "released",
            {
                "response_id": plan.response_id,
                "segment_ids": [segment.segment_id for segment in segments],
                "latency_ms": round((perf_counter() - started) * 1000, 2),
            },
            latency_ms=(perf_counter() - started) * 1000,
        )
        return TurnOutcome(
            state=state,
            draft=draft,
            proposal=proposal,
            commit_result=commit_result,
            grounded_answer=grounded_answer,
            response_plan=plan,
            speech_segments=segments,
        )

    async def _trace(
        self,
        state: ConversationState,
        event_type: str,
        component: str,
        outcome: str,
        payload: dict,
        *,
        latency_ms: float | None = None,
    ) -> None:
        await self.repository.append_event(
            TraceEvent(
                event_type=event_type,
                session_id=state.session_id,
                application_id=state.application_id,
                trace_id=state.trace_id,
                component=component,
                outcome=outcome,
                turn_id=state.current_turn_id,
                generation_id=state.generation_id,
                application_revision=state.linked_application_revision,
                state_version=state.state_version,
                latency_ms=latency_ms,
                payload=payload,
            )
        )
