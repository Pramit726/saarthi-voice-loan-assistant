from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .contracts import GroundedAnswer, ReleaseGateResult, ResponsePlan
from .enums import AllowedAction, SupportStatus


PRESSURE_PATTERNS = (
    re.compile(r"\bact now\b", re.I),
    re.compile(r"\blimited time\b", re.I),
    re.compile(r"\bdon't miss\b", re.I),
    re.compile(r"\bmust take\b", re.I),
    re.compile(r"\bguaranteed approval\b", re.I),
    re.compile(r"\bbest (loan|amount|tenure)\b", re.I),
)

FORBIDDEN_ACTION_TOKENS = {
    "submit",
    "approve",
    "reject",
    "sign",
    "mandate",
    "pay",
    "disburse",
    "credit_check",
    "kyc",
}

SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:PAN|Aadhaar|OTP)\b", re.I),
    re.compile(r"\b(?:account|card) number\b", re.I),
    re.compile(r"\b(?:tell|share|provide) (?:me )?your (?:phone number|email address)\b", re.I),
)


@dataclass(frozen=True)
class ActionRegistry:
    allowed: frozenset[AllowedAction] = frozenset(
        {
            AllowedAction.UPDATE_DRAFT,
            AllowedAction.SHOW_FACT_SHEET,
            AllowedAction.EXPORT_DRAFT,
            AllowedAction.SESSION_CONTROL,
            AllowedAction.NONE,
        }
    )

    def permits(self, action: AllowedAction) -> bool:
        return action in self.allowed

    def dispatch(self, action_name: str, callback: Callable[[], object]) -> object:
        if action_name in FORBIDDEN_ACTION_TOKENS:
            raise PermissionError(f"Action '{action_name}' does not exist in the Saarthi MVP.")
        try:
            action = AllowedAction(action_name)
        except ValueError as exc:
            raise PermissionError(f"Action '{action_name}' is not allowlisted.") from exc
        if not self.permits(action):
            raise PermissionError(f"Action '{action_name}' is not permitted.")
        return callback()


class ResponseGuard:
    """Deterministic TR-6 release gates; prompts are never the safety boundary."""

    def __init__(self, action_registry: ActionRegistry | None = None) -> None:
        self.actions = action_registry or ActionRegistry()

    def evaluate(
        self,
        plan: ResponsePlan,
        *,
        grounded_answer: GroundedAnswer | None = None,
        financial_response: bool = False,
    ) -> ResponsePlan:
        text = " ".join(plan.message_segments)
        gate_results = [
            ReleaseGateResult(
                gate="action_allowlist",
                passed=self.actions.permits(plan.allowed_action),
                reason="allowed" if self.actions.permits(plan.allowed_action) else "action_not_allowed",
            ),
            ReleaseGateResult(
                gate="neutrality",
                passed=not any(pattern.search(text) for pattern in PRESSURE_PATTERNS),
                reason="neutral" if not any(pattern.search(text) for pattern in PRESSURE_PATTERNS) else "pressure_language",
            ),
            ReleaseGateResult(
                gate="sensitive_data",
                passed=not any(pattern.search(text) for pattern in SENSITIVE_PATTERNS),
                reason="no_sensitive_request" if not any(pattern.search(text) for pattern in SENSITIVE_PATTERNS) else "sensitive_data_request",
            ),
        ]
        if grounded_answer is not None:
            supported = (
                grounded_answer.support_status is SupportStatus.SUPPORTED
                and grounded_answer.completeness_passed
                and bool(grounded_answer.supporting_fact_ids or grounded_answer.calculation_ids)
            )
            gate_results.append(
                ReleaseGateResult(
                    gate="grounding",
                    passed=supported,
                    reason="claim_evidence_linked" if supported else "unsupported_claim",
                )
            )
        if financial_response:
            gate_results.append(
                ReleaseGateResult(
                    gate="financial_labels",
                    passed=bool(plan.labelled_values),
                    reason="values_labelled" if plan.labelled_values else "missing_value_labels",
                )
            )
        return plan.model_copy(update={"release_gates": gate_results})


SAFE_FALLBACKS: dict[str, list[str]] = {
    "unsupported_product_question": [
        "The approved product sheet does not contain enough information to answer that.",
        "I can show you the written product sheet or return to the application draft.",
    ],
    "unsafe_response": [
        "I cannot safely provide that response.",
        "I can explain an approved product fact or continue the draft.",
    ],
    "provider_failure": [
        "I could not complete that explanation just now.",
        "Your confirmed draft information is unchanged. We can try again or continue.",
    ],
    "clarification": ["I did not understand that confidently. Please answer only the current question."],
}
