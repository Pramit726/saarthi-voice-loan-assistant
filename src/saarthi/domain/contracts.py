from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    AllowedAction,
    ChangeKind,
    ControlCommand,
    ConversationPhase,
    DeliveryStatus,
    DraftStatus,
    FieldId,
    JobKind,
    JobStatus,
    SessionStatus,
    SupportStatus,
    TurnAct,
    TurnRoute,
    Verdict,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class FinalTranscript(ContractModel):
    transcript_id: str = Field(default_factory=lambda: new_id("transcript"))
    session_id: str
    participant_id: str
    turn_id: str
    generation_id: int
    text: str = Field(min_length=1)
    language: str = "en-IN"
    confidence: float | None = Field(default=None, ge=0, le=1)
    started_at: datetime
    ended_at: datetime
    is_final: bool = True


class TurnProposal(ContractModel):
    proposal_id: str = Field(default_factory=lambda: new_id("proposal"))
    source_transcript_id: str
    acts: list[TurnAct]
    route: TurnRoute
    target_field: FieldId | None = None
    candidate_value: Any | None = None
    source_span: str | None = None
    reference_resolution: str | None = None
    control: ControlCommand | None = None
    uncertainty: float = Field(default=0.0, ge=0, le=1)
    rationale_code: str
    explicit_write: bool = False


class CommittedFieldValue(ContractModel):
    field_id: FieldId
    typed_value: Any
    source_turn_id: str
    source_span: str
    normalizer_version: str
    validator_version: str
    committed_at_revision: int = Field(ge=1)
    last_change_kind: ChangeKind
    updated_at: datetime = Field(default_factory=utc_now)


class FinancialProjection(ContractModel):
    projection_id: str = Field(default_factory=lambda: new_id("projection"))
    source_application_revision: int
    product_id: str
    product_version: str
    fact_set_version: str
    calculator_version: str
    requested_amount: Decimal
    annual_interest_rate_percent: Decimal
    tenure_months: int
    processing_fee: Decimal
    tax_on_processing_fee: Decimal
    total_deduction: Decimal
    net_disbursal: Decimal
    emi: Decimal
    total_repayment: Decimal
    total_interest: Decimal
    created_at: datetime = Field(default_factory=utc_now)


class FieldChangeRecord(ContractModel):
    change_id: str = Field(default_factory=lambda: new_id("change"))
    target_field: FieldId
    old_value: Any | None
    new_value: Any
    source_turn_id: str
    change_kind: ChangeKind
    before_revision: int
    after_revision: int
    changed_at: datetime = Field(default_factory=utc_now)


class DraftArtifact(ContractModel):
    artifact_id: str = Field(default_factory=lambda: new_id("artifact"))
    application_id: str
    application_revision: int
    projection_id: str | None = None
    label: str = "Draft for review - not submitted"
    generated_at: datetime = Field(default_factory=utc_now)


class ApplicationDraft(ContractModel):
    application_id: str = Field(default_factory=lambda: new_id("application"))
    owner_session_id: str
    product_id: str = "SPL-DEMO-01"
    product_version: str = "1.1"
    schema_version: str = "1.0"
    status: DraftStatus = DraftStatus.IN_PROGRESS
    revision: int = 0
    fields: dict[FieldId, CommittedFieldValue] = Field(default_factory=dict)
    current_projection: FinancialProjection | None = None
    change_history: list[FieldChangeRecord] = Field(default_factory=list)
    artifact: DraftArtifact | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ApplicationPatch(ContractModel):
    patch_id: str = Field(default_factory=lambda: new_id("patch"))
    idempotency_key: str
    session_id: str
    application_id: str
    expected_application_revision: int
    source_turn_id: str
    source_generation_id: int
    target_field: FieldId
    normalized_candidate: Any
    source_span: str
    explicit_target: bool
    confirmation_required: bool = False
    confirmed: bool = False
    change_kind: ChangeKind = ChangeKind.INITIAL
    normalizer_version: str = "field-normalizer-v1"
    validator_version: str = "field-validator-v1"


class CommitResult(ContractModel):
    accepted: bool
    reason_code: str
    previous_revision: int
    new_revision: int
    changed_field: FieldId | None = None
    previous_value: Any | None = None
    new_value: Any | None = None
    checkpoint_effect: str = "none"
    draft: ApplicationDraft | None = None


class ResumeCheckpoint(ContractModel):
    checkpoint_id: str = Field(default_factory=lambda: new_id("checkpoint"))
    pending_field: FieldId | None
    application_revision: int
    state_version: int
    resume_prompt: str
    navigation_stack: list[FieldId] = Field(default_factory=list)
    last_heard_segment_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ActiveJob(ContractModel):
    job_id: str = Field(default_factory=lambda: new_id("job"))
    kind: JobKind
    turn_id: str
    route: TurnRoute
    captured_state_version: int
    captured_generation_id: int
    captured_application_revision: int
    status: JobStatus = JobStatus.ACTIVE
    deadline_at: datetime | None = None


class SpeechSegment(ContractModel):
    response_id: str
    segment_id: str = Field(default_factory=lambda: new_id("segment"))
    order: int = Field(ge=0)
    generation_id: int
    text: str
    value_labels: dict[str, str] = Field(default_factory=dict)
    delivery_status: DeliveryStatus = DeliveryStatus.PLANNED
    heard_character_count: int = 0
    synthesis_metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationState(ContractModel):
    session_id: str
    application_id: str
    trace_id: str = Field(default_factory=lambda: new_id("trace"))
    participant_id: str
    channel: str = "web_voice"
    language: str = "en-IN"
    status: SessionStatus = SessionStatus.ACTIVE
    phase: ConversationPhase = ConversationPhase.COLLECTION
    pending_field: FieldId | None = FieldId.REQUESTED_AMOUNT
    resume_checkpoint: ResumeCheckpoint | None = None
    navigation_stack: list[FieldId] = Field(default_factory=list)
    current_turn_id: str | None = None
    current_proposal: TurnProposal | None = None
    pending_write_confirmation: TurnProposal | None = None
    state_version: int = 0
    generation_id: int = 0
    linked_application_revision: int = 0
    active_jobs: dict[str, ActiveJob] = Field(default_factory=dict)
    current_fact_ids: list[str] = Field(default_factory=list)
    current_calculation_id: str | None = None
    output_queue: list[SpeechSegment] = Field(default_factory=list)
    last_fully_heard_response: list[SpeechSegment] = Field(default_factory=list)
    last_safe_prompt: str | None = None
    failure_component: str | None = None
    failure_reason: str | None = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ProductFact(ContractModel):
    fact_id: str
    product_id: str
    product_version: str
    fact_set_version: str
    status: str = "approved"
    fact_type: str
    topic: str
    text: str
    aliases: list[str] = Field(default_factory=list)
    language: str = "en"
    numeric_values: dict[str, Decimal] = Field(default_factory=dict)
    source_section: str


class RetrievedFact(ContractModel):
    fact: ProductFact
    score: float = 1.0


class GroundedClaim(ContractModel):
    claim_id: str = Field(default_factory=lambda: new_id("claim"))
    text: str
    fact_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)


class GroundedAnswer(ContractModel):
    answer_id: str = Field(default_factory=lambda: new_id("answer"))
    product_id: str
    product_version: str
    fact_set_version: str
    question_route: TurnRoute
    claims: list[GroundedClaim] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    labelled_values: dict[str, str] = Field(default_factory=dict)
    support_status: SupportStatus
    completeness_passed: bool
    abstention_reason: str | None = None


class ReleaseGateResult(ContractModel):
    gate: str
    passed: bool
    reason: str


class ResponsePlan(ContractModel):
    response_id: str = Field(default_factory=lambda: new_id("response"))
    purpose: str
    message_segments: list[str]
    labelled_values: dict[str, str] = Field(default_factory=dict)
    required_disclosures: list[str] = Field(default_factory=list)
    allowed_action: AllowedAction = AllowedAction.NONE
    resume_instruction: str | None = None
    release_gates: list[ReleaseGateResult] = Field(default_factory=list)
    fallback_code: str | None = None

    @property
    def releasable(self) -> bool:
        return all(gate.passed for gate in self.release_gates)


class TraceEvent(ContractModel):
    event_id: str = Field(default_factory=lambda: new_id("event"))
    event_type: str
    occurred_at: datetime = Field(default_factory=utc_now)
    session_id: str
    application_id: str
    trace_id: str
    component: str
    outcome: str
    turn_id: str | None = None
    generation_id: int
    application_revision: int
    state_version: int
    latency_ms: float | None = None
    correlation_id: str | None = None
    parent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class AcceptanceResult(ContractModel):
    verdict: Verdict
    hard_gate_failures: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    target_misses: list[str] = Field(default_factory=list)


class TurnOutcome(ContractModel):
    state: ConversationState
    draft: ApplicationDraft
    proposal: TurnProposal | None = None
    commit_result: CommitResult | None = None
    grounded_answer: GroundedAnswer | None = None
    response_plan: ResponsePlan
    speech_segments: list[SpeechSegment] = Field(default_factory=list)
