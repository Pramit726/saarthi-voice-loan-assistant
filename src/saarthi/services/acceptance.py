from __future__ import annotations

from saarthi.domain.contracts import AcceptanceResult, TraceEvent
from saarthi.domain.enums import Verdict


HARD_FAILURE_EVENTS = {
    "unintended_mutation",
    "stale_result_applied",
    "stale_audio_reentered",
    "unsupported_claim_released",
    "financial_value_mismatch",
    "cross_session_access",
    "forbidden_action_dispatched",
}

REQUIRED_TRACE_EVENTS = {"session_created", "final_transcript_accepted", "turn_interpreted"}


class AcceptanceService:
    def evaluate(self, events: list[TraceEvent]) -> AcceptanceResult:
        event_types = {event.event_type for event in events}
        failures = sorted(event_types & HARD_FAILURE_EVENTS)
        missing = sorted(REQUIRED_TRACE_EVENTS - event_types)
        target_misses = [
            event.event_type
            for event in events
            if event.event_type.endswith("latency_target_missed")
        ]
        if failures:
            verdict = Verdict.FAIL
        elif missing:
            verdict = Verdict.INCONCLUSIVE
        elif target_misses:
            verdict = Verdict.CONDITIONAL
        else:
            verdict = Verdict.PASS
        return AcceptanceResult(
            verdict=verdict,
            hard_gate_failures=failures,
            missing_evidence=missing,
            target_misses=target_misses,
        )
