from __future__ import annotations

from collections import defaultdict
from math import ceil
from statistics import mean, median

from saarthi.domain.contracts import ConversationState, TraceEvent
from saarthi.domain.enums import Verdict
from saarthi.services.acceptance import HARD_FAILURE_EVENTS, AcceptanceService


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * quantile) - 1)]


class EvidenceService:
    def __init__(
        self,
        acceptance: AcceptanceService,
        *,
        normal_latency_target_ms: int,
        grounded_latency_target_ms: int,
    ) -> None:
        self.acceptance = acceptance
        self.normal_latency_target_ms = normal_latency_target_ms
        self.grounded_latency_target_ms = grounded_latency_target_ms

    def session_summaries(
        self, states: list[ConversationState], events: list[TraceEvent]
    ) -> list[dict]:
        grouped = self._group_events(events)
        summaries = []
        for state in states:
            session_events = grouped[state.session_id]
            turns = {
                event.turn_id
                for event in session_events
                if event.event_type == "final_transcript_accepted" and event.turn_id
            }
            summaries.append(
                {
                    "session_id": state.session_id,
                    "created_at": state.created_at,
                    "updated_at": state.updated_at,
                    "status": state.status.value,
                    "pending_field": (
                        state.pending_field.value if state.pending_field else None
                    ),
                    "application_revision": state.linked_application_revision,
                    "turn_count": len(turns),
                    "verdict": self.acceptance.evaluate(session_events).verdict.value,
                }
            )
        return summaries

    def aggregate(
        self, states: list[ConversationState], events: list[TraceEvent]
    ) -> dict:
        grouped = self._group_events(events)
        accepted_turns = {
            (event.session_id, event.turn_id)
            for event in events
            if event.event_type == "final_transcript_accepted" and event.turn_id
        }
        interpreted_turns = {
            (event.session_id, event.turn_id)
            for event in events
            if event.event_type == "turn_interpreted" and event.turn_id
        }
        route_by_turn = {
            (event.session_id, event.turn_id): event.outcome
            for event in events
            if event.event_type == "turn_interpreted" and event.turn_id
        }
        response_events = [
            event
            for event in events
            if event.event_type == "response_released" and event.latency_ms is not None
        ]
        latencies = [float(event.latency_ms) for event in response_events]
        target_hits = 0
        for event in response_events:
            route = route_by_turn.get((event.session_id, event.turn_id))
            target = (
                self.grounded_latency_target_ms
                if route in {"field_doubt", "product_question", "calculation"}
                else self.normal_latency_target_ms
            )
            target_hits += int(float(event.latency_ms) <= target)

        evaluated = [
            state
            for state in states
            if any(
                event.event_type == "final_transcript_accepted"
                for event in grouped[state.session_id]
            )
        ]
        passed = sum(
            self.acceptance.evaluate(grouped[state.session_id]).verdict is Verdict.PASS
            for state in evaluated
        )
        return {
            "session_count": len(states),
            "evaluated_session_count": len(evaluated),
            "turn_count": len(accepted_turns),
            "interpreter_success_rate_pct": self._rate(
                len(interpreted_turns), len(accepted_turns)
            ),
            "response_latency_sample_count": len(latencies),
            "response_latency_average_ms": round(mean(latencies), 1)
            if latencies
            else 0.0,
            "response_latency_p50_ms": round(median(latencies), 1)
            if latencies
            else 0.0,
            "response_latency_p95_ms": round(_percentile(latencies, 0.95), 1),
            "latency_target_attainment_pct": self._rate(
                target_hits, len(response_events)
            ),
            "pass_rate_pct": self._rate(passed, len(evaluated)),
            "grounded_answer_count": sum(
                event.event_type == "grounding_decided" for event in events
            ),
            "failed_closed_count": sum(
                event.outcome == "failed_closed" for event in events
            ),
            "hard_failure_count": sum(
                event.event_type in HARD_FAILURE_EVENTS for event in events
            ),
        }

    @staticmethod
    def _group_events(events: list[TraceEvent]) -> defaultdict[str, list[TraceEvent]]:
        grouped: defaultdict[str, list[TraceEvent]] = defaultdict(list)
        for event in events:
            grouped[event.session_id].append(event)
        return grouped

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        return round(100 * numerator / denominator, 1) if denominator else 0.0
