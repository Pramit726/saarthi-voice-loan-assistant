import pytest

from saarthi.domain.contracts import ResponsePlan
from saarthi.domain.enums import AllowedAction
from saarthi.domain.policies import ActionRegistry, ResponseGuard


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Act now because this loan is available for a limited time.",
        "You must take this loan.",
        "This is the best tenure for you.",
        "You have guaranteed approval.",
        "Don't miss this offer.",
        "Please provide your PAN.",
        "Tell me your Aadhaar.",
        "Share your OTP.",
        "Provide your bank account number.",
        "Tell me your phone number.",
    ],
)
def test_adversarial_response_is_blocked(unsafe_text):
    plan = ResponsePlan(purpose="adversarial", message_segments=[unsafe_text])
    guarded = ResponseGuard().evaluate(plan)
    assert not guarded.releasable


@pytest.mark.parametrize(
    "action",
    [
        "submit",
        "approve",
        "reject",
        "sign",
        "mandate",
        "pay",
        "disburse",
        "credit_check",
        "kyc",
    ],
)
def test_forbidden_action_is_physically_absent(action):
    with pytest.raises(PermissionError):
        ActionRegistry().dispatch(action, lambda: "should not execute")


def test_decline_is_treated_neutrally():
    plan = ResponsePlan(
        purpose="decline",
        message_segments=[
            "Okay. The draft is cancelled, and no loan action was taken."
        ],
        allowed_action=AllowedAction.SESSION_CONTROL,
    )
    assert ResponseGuard().evaluate(plan).releasable
