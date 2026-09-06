from __future__ import annotations

from decimal import Decimal

from saarthi.domain.contracts import CommitResult, GroundedAnswer, ResponsePlan
from saarthi.domain.enums import AllowedAction, ControlCommand, SupportStatus
from saarthi.domain.fields import FIELD_DEFINITIONS
from saarthi.domain.policies import SAFE_FALLBACKS, ResponseGuard


def _display_value(value: object) -> str:
    if isinstance(value, Decimal):
        return f"Rs. {value:,.2f}"
    return str(value)


class ResponsePlanner:
    def __init__(self, guard: ResponseGuard | None = None) -> None:
        self.guard = guard or ResponseGuard()

    def for_commit(self, result: CommitResult, *, next_field=None) -> ResponsePlan:
        if not result.accepted:
            plan = ResponsePlan(
                purpose="clarification",
                message_segments=SAFE_FALLBACKS["clarification"],
                fallback_code=result.reason_code,
            )
            return self.guard.evaluate(plan)
        segments = [
            f"I recorded {_display_value(result.new_value)} for {result.changed_field.value.replace('_', ' ')}."
        ]
        resume = None
        if next_field:
            resume = FIELD_DEFINITIONS[next_field].prompt
            segments.append(resume)
        else:
            segments.append(
                "Your draft is ready for review. It has not been submitted."
            )
        plan = ResponsePlan(
            purpose="field_commit",
            message_segments=segments,
            allowed_action=AllowedAction.UPDATE_DRAFT,
            resume_instruction=resume,
        )
        return self.guard.evaluate(plan)

    def for_grounded_answer(
        self, answer: GroundedAnswer, *, resume_prompt: str | None
    ) -> ResponsePlan:
        if (
            answer.support_status is not SupportStatus.SUPPORTED
            or not answer.completeness_passed
        ):
            plan = ResponsePlan(
                purpose="abstention",
                message_segments=SAFE_FALLBACKS["unsupported_product_question"]
                + ([resume_prompt] if resume_prompt else []),
                allowed_action=AllowedAction.SHOW_FACT_SHEET,
                resume_instruction=resume_prompt,
                fallback_code=answer.abstention_reason
                or "unsupported_product_question",
            )
            return self.guard.evaluate(plan)

        segments = [claim.text for claim in answer.claims]
        if resume_prompt:
            segments.append(resume_prompt)
        plan = ResponsePlan(
            purpose="grounded_explanation",
            message_segments=segments,
            labelled_values=dict(answer.labelled_values),
            resume_instruction=resume_prompt,
        )
        return self.guard.evaluate(
            plan,
            grounded_answer=answer,
            financial_response=bool(answer.calculation_ids),
        )

    def for_control(
        self, command: ControlCommand, *, repeat_text: list[str] | None = None
    ) -> ResponsePlan:
        messages = {
            ControlCommand.STOP: [],
            ControlCommand.CANCEL: [
                "The demonstration draft is cancelled. No application was submitted."
            ],
            ControlCommand.PAUSE: [
                "Paused. Your confirmed draft information is preserved."
            ],
            ControlCommand.RESUME: ["We can continue from the saved question."],
            ControlCommand.REPEAT: repeat_text
            or ["There is no fully heard response to repeat yet."],
            ControlCommand.GO_BACK: ["Going back one question."],
            ControlCommand.SHOW_SUMMARY: [
                "I will show the current draft. It has not been submitted."
            ],
        }
        plan = ResponsePlan(
            purpose=f"control_{command.value}",
            message_segments=messages[command],
            allowed_action=AllowedAction.SESSION_CONTROL,
        )
        return self.guard.evaluate(plan)

    def safe_fallback(self, code: str = "provider_failure") -> ResponsePlan:
        plan = ResponsePlan(
            purpose="fallback",
            message_segments=SAFE_FALLBACKS.get(
                code, SAFE_FALLBACKS["provider_failure"]
            ),
            fallback_code=code,
        )
        return self.guard.evaluate(plan)
