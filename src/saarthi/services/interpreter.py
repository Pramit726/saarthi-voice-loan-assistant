from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from saarthi.domain.contracts import ConversationState, FinalTranscript, TurnProposal
from saarthi.domain.enums import ControlCommand, FieldId, TurnAct, TurnRoute
from saarthi.providers.groq import GroqStructuredClient, InterpretationPayload


CONTROL_PATTERNS: tuple[tuple[ControlCommand, re.Pattern[str]], ...] = (
    (ControlCommand.CANCEL, re.compile(r"\b(cancel|end the application|delete the draft)\b", re.I)),
    (ControlCommand.STOP, re.compile(r"\b(stop|stop speaking|be quiet)\b", re.I)),
    (ControlCommand.PAUSE, re.compile(r"\b(pause|hold on|wait)\b", re.I)),
    (ControlCommand.RESUME, re.compile(r"\b(resume|continue|carry on)\b", re.I)),
    (ControlCommand.REPEAT, re.compile(r"\b(repeat|say that again|once more)\b", re.I)),
    (ControlCommand.GO_BACK, re.compile(r"\b(go back|previous question|previous field)\b", re.I)),
    (ControlCommand.SHOW_SUMMARY, re.compile(r"\b(show|read) (my )?(summary|draft)\b", re.I)),
)


@dataclass(frozen=True)
class FewShotExample:
    text: str
    context_field: FieldId
    payload: dict[str, object]


EXAMPLES: tuple[FewShotExample, ...] = (
    FewShotExample("one lakh rupees", FieldId.REQUESTED_AMOUNT, {"acts": ["answer"], "route": "field_answer", "target_field": "requested_amount", "candidate_value": 100000, "explicit_write": True}),
    FewShotExample("what does tenure mean", FieldId.PREFERRED_TENURE, {"acts": ["doubt"], "route": "field_doubt", "target_field": "preferred_tenure", "candidate_value": None, "explicit_write": False}),
    FewShotExample("twelve months, but what will the EMI be", FieldId.PREFERRED_TENURE, {"acts": ["answer", "doubt"], "route": "calculation", "target_field": "preferred_tenure", "candidate_value": "12 months", "explicit_write": False}),
    FewShotExample("change the amount to eighty thousand", FieldId.LOAN_PURPOSE, {"acts": ["correction"], "route": "correction", "target_field": "requested_amount", "candidate_value": 80000, "explicit_write": True}),
    FewShotExample("is the processing fee part of EMI", FieldId.LOAN_PURPOSE, {"acts": ["doubt"], "route": "product_question", "target_field": None, "candidate_value": None, "explicit_write": False}),
    FewShotExample("I am salaried", FieldId.EMPLOYMENT_TYPE, {"acts": ["answer"], "route": "field_answer", "target_field": "employment_type", "candidate_value": "salaried", "explicit_write": True}),
    FewShotExample("I don't know", FieldId.MONTHLY_INCOME, {"acts": ["ambiguous"], "route": "clarification", "target_field": "monthly_income", "candidate_value": None, "explicit_write": False}),
    FewShotExample("zero", FieldId.EXISTING_REPAYMENTS, {"acts": ["answer"], "route": "field_answer", "target_field": "existing_repayments", "candidate_value": 0, "explicit_write": True}),
)


class TurnInterpreter(Protocol):
    async def interpret(self, transcript: FinalTranscript, state: ConversationState) -> TurnProposal: ...


def _lexical_score(left: str, right: str) -> int:
    left_tokens = set(re.findall(r"[a-z0-9]+", left.casefold()))
    right_tokens = set(re.findall(r"[a-z0-9]+", right.casefold()))
    return len(left_tokens & right_tokens)


class RetrievedFewShotInterpreter:
    def __init__(self, client: GroqStructuredClient, *, example_count: int = 5) -> None:
        self.client = client
        self.example_count = example_count

    async def interpret(self, transcript: FinalTranscript, state: ConversationState) -> TurnProposal:
        direct_control = self._direct_control(transcript)
        if direct_control:
            return direct_control
        confirmation = self._pending_confirmation(transcript, state)
        if confirmation:
            return confirmation

        ranked = sorted(
            EXAMPLES,
            key=lambda example: (
                example.context_field == state.pending_field,
                _lexical_score(transcript.text, example.text),
            ),
            reverse=True,
        )[: self.example_count]
        examples = [
            {"text": example.text, "pending_field": example.context_field.value, "output": example.payload}
            for example in ranked
        ]
        system = """You classify one finalized turn in a synthetic voice loan-draft workflow.
Return only the required schema. Models never write application state.
Routes: field_answer, field_doubt, product_question, calculation, correction, control, clarification, fallback.
Acts: answer, doubt, correction, control, mixed, ambiguous.
A question, command, uncertainty, or mixed answer-plus-doubt must never be an explicit write.
Only use a target field when it is explicit or is the single pending field for a plain answer.
Normalize money candidates to numeric rupees, tenure to integer months, employment to salaried or self-employed,
and contact preference to phone or email. Preserve the exact spoken phrase in source_span.
Never request or extract real PAN, Aadhaar, bank account, OTP, phone number, or email address."""
        user = json.dumps(
            {
                "pending_field": state.pending_field.value if state.pending_field else None,
                "phase": state.phase.value,
                "transcript": transcript.text,
                "confidence": transcript.confidence,
                "retrieved_examples": examples,
            },
            ensure_ascii=False,
        )
        payload = await self.client.interpret(system=system, user=user)
        return self._guard(payload, transcript, state)

    @staticmethod
    def _direct_control(transcript: FinalTranscript) -> TurnProposal | None:
        for command, pattern in CONTROL_PATTERNS:
            if pattern.search(transcript.text):
                return TurnProposal(
                    source_transcript_id=transcript.transcript_id,
                    acts=[TurnAct.CONTROL],
                    route=TurnRoute.CONTROL,
                    control=command,
                    uncertainty=0,
                    rationale_code="deterministic_control_match",
                    explicit_write=False,
                )
        return None

    @staticmethod
    def _pending_confirmation(
        transcript: FinalTranscript, state: ConversationState
    ) -> TurnProposal | None:
        pending = state.pending_write_confirmation
        if pending is None:
            return None
        text = transcript.text.casefold().strip()
        if re.fullmatch(r"(?:yes|yes please|confirm|correct|haan|hanji)[.! ]*", text):
            return TurnProposal(
                source_transcript_id=transcript.transcript_id,
                acts=list(pending.acts),
                route=(TurnRoute.CORRECTION if TurnAct.CORRECTION in pending.acts else TurnRoute.FIELD_ANSWER),
                target_field=pending.target_field,
                candidate_value=pending.candidate_value,
                source_span=pending.source_span or transcript.text,
                reference_resolution=pending.reference_resolution,
                uncertainty=0,
                rationale_code="confirmed_pending_write",
                explicit_write=True,
            )
        if re.fullmatch(r"(?:no|do not|don't|cancel that|nahi)[.! ]*", text):
            return TurnProposal(
                source_transcript_id=transcript.transcript_id,
                acts=[TurnAct.AMBIGUOUS],
                route=TurnRoute.FALLBACK,
                target_field=pending.target_field,
                uncertainty=0,
                rationale_code="discard_pending_write",
                explicit_write=False,
            )
        return None

    @staticmethod
    def _guard(
        payload: InterpretationPayload,
        transcript: FinalTranscript,
        state: ConversationState,
    ) -> TurnProposal:
        acts = [TurnAct(item) for item in payload.acts]
        route = TurnRoute(payload.route)
        target = FieldId(payload.target_field) if payload.target_field else None
        control = ControlCommand(payload.control) if payload.control else None
        confidence_uncertain = transcript.confidence is not None and transcript.confidence < 0.70
        unsafe_write_shape = (
            route not in {TurnRoute.FIELD_ANSWER, TurnRoute.CORRECTION}
            or any(act in {TurnAct.DOUBT, TurnAct.CONTROL, TurnAct.AMBIGUOUS, TurnAct.MIXED} for act in acts)
            or payload.candidate_value is None
            or target is None
        )
        if confidence_uncertain:
            acts = [TurnAct.AMBIGUOUS]
            route = TurnRoute.CLARIFICATION
            target = state.pending_field
        explicit_write = bool(payload.explicit_write and not unsafe_write_shape and not confidence_uncertain)
        if route is TurnRoute.FIELD_ANSWER and target is None:
            target = state.pending_field
        return TurnProposal(
            source_transcript_id=transcript.transcript_id,
            acts=acts,
            route=route,
            target_field=target,
            candidate_value=payload.candidate_value,
            source_span=payload.source_span,
            reference_resolution=payload.reference_resolution,
            control=control,
            uncertainty=max(payload.uncertainty, 0.7 if confidence_uncertain else 0.0),
            rationale_code=("low_stt_confidence" if confidence_uncertain else payload.rationale_code),
            explicit_write=explicit_write,
        )
