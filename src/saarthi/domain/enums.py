from enum import StrEnum


class FieldId(StrEnum):
    REQUESTED_AMOUNT = "requested_amount"
    LOAN_PURPOSE = "loan_purpose"
    PREFERRED_TENURE = "preferred_tenure"
    EMPLOYMENT_TYPE = "employment_type"
    MONTHLY_INCOME = "monthly_income"
    EXISTING_REPAYMENTS = "existing_repayments"
    CITY = "city"
    CONTACT_PREFERENCE = "contact_preference"


class DraftStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    READY_FOR_REVIEW = "ready_for_review"
    COMPLETED_DRAFT = "completed_draft"
    CANCELLED = "cancelled"


class ChangeKind(StrEnum):
    INITIAL = "initial"
    CORRECTION = "correction"


class TurnAct(StrEnum):
    ANSWER = "answer"
    DOUBT = "doubt"
    CORRECTION = "correction"
    CONTROL = "control"
    MIXED = "mixed"
    AMBIGUOUS = "ambiguous"


class TurnRoute(StrEnum):
    FIELD_ANSWER = "field_answer"
    FIELD_DOUBT = "field_doubt"
    PRODUCT_QUESTION = "product_question"
    CALCULATION = "calculation"
    CORRECTION = "correction"
    CONTROL = "control"
    CLARIFICATION = "clarification"
    FALLBACK = "fallback"


class ControlCommand(StrEnum):
    STOP = "stop"
    CANCEL = "cancel"
    PAUSE = "pause"
    RESUME = "resume"
    REPEAT = "repeat"
    GO_BACK = "go_back"
    SHOW_SUMMARY = "show_summary"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"


class ConversationPhase(StrEnum):
    COLLECTION = "collection"
    EXPLANATION = "explanation"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    REVIEW = "review"
    FALLBACK = "fallback"
    STOPPED = "stopped"


class JobKind(StrEnum):
    STT = "stt"
    INTERPRETATION = "interpretation"
    RETRIEVAL = "retrieval"
    CALCULATION = "calculation"
    SAFETY = "safety"
    TTS = "tts"


class JobStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    STALE = "stale"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    PLANNED = "planned"
    SYNTHESIZING = "synthesizing"
    QUEUED = "queued"
    PLAYING = "playing"
    INTERRUPTED = "interrupted"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class SupportStatus(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"


class AllowedAction(StrEnum):
    UPDATE_DRAFT = "update_draft"
    SHOW_FACT_SHEET = "show_fact_sheet"
    EXPORT_DRAFT = "export_draft"
    SESSION_CONTROL = "session_control"
    NONE = "none"


class Verdict(StrEnum):
    PASS = "pass"
    CONDITIONAL = "conditional"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
