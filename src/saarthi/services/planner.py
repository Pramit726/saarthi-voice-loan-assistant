from __future__ import annotations

from decimal import Decimal

from saarthi.domain.contracts import (
    CommitResult,
    GroundedAnswer,
    ResponsePlan,
    TurnProposal,
)
from saarthi.domain.enums import AllowedAction, ControlCommand, FieldId, SupportStatus
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
            segments[0] += f" Next question. {resume}"
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
        self,
        command: ControlCommand,
        *,
        repeat_text: list[str] | None = None,
        resume_prompt: str | None = None,
    ) -> ResponsePlan:
        messages = {
            ControlCommand.STOP: [],
            ControlCommand.CANCEL: [
                "The demonstration draft is cancelled. No application was submitted."
            ],
            ControlCommand.PAUSE: [
                "Paused. Your confirmed draft information is preserved."
            ],
            ControlCommand.RESUME: ["We can continue from the saved question."]
            + ([resume_prompt] if resume_prompt else []),
            ControlCommand.REPEAT: repeat_text
            or ["There is no fully heard response to repeat yet."],
            ControlCommand.GO_BACK: ["Going back one question."]
            + ([resume_prompt] if resume_prompt else []),
            ControlCommand.SHOW_SUMMARY: [
                "I will show the current draft. It has not been submitted."
            ],
        }
        plan = ResponsePlan(
            purpose=f"control_{command.value}",
            message_segments=messages[command],
            allowed_action=AllowedAction.SESSION_CONTROL,
            resume_instruction=(
                resume_prompt
                if command in {ControlCommand.RESUME, ControlCommand.GO_BACK}
                else None
            ),
        )
        return self.guard.evaluate(plan)

    def for_hedged_value(self, proposal: TurnProposal) -> ResponsePlan:
        """Ask for explicit confirmation instead of committing an estimate."""

        field_label = (
            proposal.target_field.value.replace("_", " ")
            if proposal.target_field
            else "that value"
        )
        value = proposal.candidate_value
        if proposal.target_field in {
            FieldId.REQUESTED_AMOUNT,
            FieldId.MONTHLY_INCOME,
            FieldId.EXISTING_REPAYMENTS,
        }:
            try:
                rendered_value = f"{float(value):,.0f} rupees"
            except (TypeError, ValueError):
                rendered_value = str(value)
        elif proposal.target_field is FieldId.PREFERRED_TENURE:
            rendered_value = f"{value} months"
        else:
            rendered_value = str(value)
        plan = ResponsePlan(
            purpose="clarify_hedged_value",
            message_segments=[
                f"I understood your {field_label} as {rendered_value}. Should I record that?"
            ],
        )
        return self.guard.evaluate(plan)

    def for_correction_confirmation(
        self, proposal: TurnProposal, *, current_value: object | None
    ) -> ResponsePlan:
        field_label = proposal.target_field.value.replace("_", " ")

        def value_text(value: object | None) -> str:
            if value is None:
                return "not answered"
            if proposal.target_field in {
                FieldId.REQUESTED_AMOUNT,
                FieldId.MONTHLY_INCOME,
                FieldId.EXISTING_REPAYMENTS,
            }:
                return f"Rs. {Decimal(str(value)):,.2f}"
            if proposal.target_field is FieldId.PREFERRED_TENURE:
                return f"{value} months"
            return str(value)

        plan = ResponsePlan(
            purpose="confirm_correction",
            message_segments=[
                f"The current {field_label} is {value_text(current_value)}.",
                f"Should I change it to {value_text(proposal.candidate_value)}? Please say yes or no.",
            ],
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
