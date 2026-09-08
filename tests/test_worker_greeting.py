from saarthi.agent.worker import build_opening_greeting


def test_opening_greeting_orients_borrower_before_first_question():
    greeting = build_opening_greeting(
        "What loan amount would you like to use for this demonstration draft?"
    )

    assert greeting.startswith(
        "Welcome to Saarthi, your voice-first loan guidance assistant."
    )
    assert "creates a reviewable draft only" in greeting
    assert "does not approve or submit a loan" in greeting
    assert "interrupt me anytime" in greeting
    assert greeting.endswith(
        "What loan amount would you like to use for this demonstration draft?"
    )
