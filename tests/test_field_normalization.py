import pytest

from saarthi.domain.enums import FieldId
from saarthi.domain.fields import (
    FieldValidationError,
    normalise_and_validate,
    suggest_indian_city,
)


@pytest.mark.parametrize(
    ("spoken_answer", "expected_city"),
    [
        ("Pune", "Pune"),
        ("my city is Pune", "Pune"),
        ("The city would be Bengaluru.", "Bengaluru"),
        ("I live in New Delhi", "New Delhi"),
        ("I am from Navi Mumbai", "Navi Mumbai"),
        ("please record my city as Pune, Maharashtra", "Pune"),
        ("my city is Pune full", "Pune"),
        ("poooning", "Pune"),
        ("Bengluru", "Bengaluru"),
        ("Bingloru", "Bengaluru"),
        ("Banglore", "Bengaluru"),
        ("Bombay", "Mumbai"),
        ("Durgapur", "Durgapur"),
        ("Hydrabad", "Hyderabad"),
    ],
)
def test_city_normalizer_extracts_city_from_spoken_answer(
    spoken_answer: str, expected_city: str
) -> None:
    assert normalise_and_validate(FieldId.CITY, spoken_answer) == expected_city


@pytest.mark.parametrize("spoken_answer", [".", "I want", "Gotham", "Mumbai or Pune"])
def test_city_rejects_unmatched_or_ambiguous_text(spoken_answer: str) -> None:
    with pytest.raises(FieldValidationError):
        normalise_and_validate(FieldId.CITY, spoken_answer)


@pytest.mark.parametrize(
    ("spoken_answer", "expected_purpose"),
    [
        ("education for my daughter", "education"),
        ("I want to renovate my home", "home renovation"),
        ("House repairs", "home renovation"),
        ("I want this for home repairs", "home renovation"),
        ("I need to fix my leaking roof", "home renovation"),
        ("my daughter's coaching classes", "education"),
        ("hospital treatment", "medical expenses"),
        ("to clear my credit card dues", "debt consolidation"),
        ("I need a laptop", "consumer purchase"),
        ("family emergency", "personal expenses"),
    ],
)
def test_loan_purpose_maps_to_bounded_taxonomy(
    spoken_answer: str, expected_purpose: str
) -> None:
    assert normalise_and_validate(FieldId.LOAN_PURPOSE, spoken_answer) == expected_purpose


@pytest.mark.parametrize("spoken_answer", [".", "I want", "something", "wedding and travel"])
def test_loan_purpose_rejects_filler_and_multiple_purposes(spoken_answer: str) -> None:
    with pytest.raises(FieldValidationError):
        normalise_and_validate(FieldId.LOAN_PURPOSE, spoken_answer)


@pytest.mark.parametrize(
    ("spoken_answer", "expected_preference"),
    [
        ("please call me", "phone"),
        ("I prefer telephone", "phone"),
        ("send it by email", "email"),
        ("a written follow-up", "email"),
    ],
)
def test_contact_preference_requires_an_explicit_supported_channel(
    spoken_answer: str, expected_preference: str
) -> None:
    assert (
        normalise_and_validate(FieldId.CONTACT_PREFERENCE, spoken_answer)
        == expected_preference
    )


@pytest.mark.parametrize(
    "spoken_answer", [".", "I want", "WhatsApp", "phone or email", "female"]
)
def test_contact_preference_rejects_unrelated_or_ambiguous_text(
    spoken_answer: str,
) -> None:
    with pytest.raises(FieldValidationError):
        normalise_and_validate(FieldId.CONTACT_PREFERENCE, spoken_answer)


@pytest.mark.parametrize(
    ("spoken_answer", "expected_type"),
    [
        ("I own a business", "self-employed"),
        ("I run my own shop", "self-employed"),
        ("I do independent consulting", "self-employed"),
        ("I work for a private company", "salaried"),
        ("I am on my employer's payroll", "salaried"),
    ],
)
def test_employment_type_handles_natural_descriptions(
    spoken_answer: str, expected_type: str
) -> None:
    assert (
        normalise_and_validate(FieldId.EMPLOYMENT_TYPE, spoken_answer)
        == expected_type
    )


@pytest.mark.parametrize("canonical", ["salaried", "self-employed"])
def test_employment_canonical_values_are_idempotent(canonical: str) -> None:
    first = normalise_and_validate(FieldId.EMPLOYMENT_TYPE, canonical)
    assert normalise_and_validate(FieldId.EMPLOYMENT_TYPE, first) == canonical


def test_city_gazetteer_suggests_but_does_not_silently_commit_fuzzy_match() -> None:
    with pytest.raises(FieldValidationError):
        normalise_and_validate(FieldId.CITY, "Bangaloroo")

    suggestion = suggest_indian_city("Bangaloroo")
    assert suggestion is not None
    assert suggestion.city == "Bengaluru"
    assert suggestion.source == "geonames_offline"


def test_city_gazetteer_does_not_suggest_unrelated_place() -> None:
    assert suggest_indian_city("Gotham") is None
