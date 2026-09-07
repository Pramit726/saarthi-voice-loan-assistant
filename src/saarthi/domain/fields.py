from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .enums import FieldId


class FieldValidationError(ValueError):
    def __init__(self, field_id: FieldId, code: str, message: str) -> None:
        super().__init__(message)
        self.field_id = field_id
        self.code = code
        self.message = message


@dataclass(frozen=True)
class FieldDefinition:
    field_id: FieldId
    prompt: str
    normalizer: Callable[[Any], Any]
    validator: Callable[[Any], None]
    requires_correction_confirmation: bool = True


def _clean_text(value: Any) -> str:
    text = " ".join(str(value).strip().split())
    if not text:
        raise ValueError("A non-empty answer is required.")
    return text


def _normalise_money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    text = _clean_text(value).lower().replace(",", "")
    text = re.sub(r"(?:rs\.?|inr|rupees?)", "", text).strip()
    multiplier = Decimal(1)
    if re.search(r"\b(?:lakh|lac)\b", text):
        multiplier = Decimal(100000)
        text = re.sub(r"\b(?:lakh|lac)s?\b", "", text).strip()
    elif re.search(r"\bthousand\b", text):
        multiplier = Decimal(1000)
        text = re.sub(r"\bthousand\b", "", text).strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        word_value = _number_words_to_decimal(text)
        if word_value is None:
            raise ValueError("I could not identify a monetary amount.")
        return (word_value * multiplier).quantize(Decimal("0.01"))
    try:
        return (Decimal(match.group()) * multiplier).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("The monetary amount is invalid.") from exc


SMALL_NUMBERS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _number_words_to_decimal(text: str) -> Decimal | None:
    tokens = re.findall(r"[a-z]+", text.casefold().replace("lac", "lakh"))
    current = 0
    total = 0
    recognized = False
    for token in tokens:
        if token in SMALL_NUMBERS:
            current += SMALL_NUMBERS[token]
            recognized = True
        elif token in TENS:
            current += TENS[token]
            recognized = True
        elif token == "hundred":
            current = max(current, 1) * 100
            recognized = True
        elif token == "thousand":
            total += max(current, 1) * 1_000
            current = 0
            recognized = True
        elif token == "lakh":
            total += max(current, 1) * 100_000
            current = 0
            recognized = True
    return Decimal(total + current) if recognized else None


def _normalise_tenure(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = _clean_text(value).lower()
    match = re.search(r"\d+", text)
    if not match:
        word_value = _number_words_to_decimal(text)
        if word_value is None or word_value != word_value.to_integral_value():
            raise ValueError("I could not identify the tenure.")
        count = int(word_value)
    else:
        count = int(match.group())
    if "year" in text:
        count *= 12
    return count


def _normalise_employment(value: Any) -> str:
    text = _clean_text(value).lower().replace("_", "-")
    if "self" in text or "business" in text or "freelance" in text:
        return "self-employed"
    if "salary" in text or "salaried" in text or "employee" in text:
        return "salaried"
    return text


def _normalise_contact(value: Any) -> str:
    text = _clean_text(value).lower()
    if any(token in text for token in ("call", "phone", "voice")):
        return "phone"
    if any(token in text for token in ("email", "mail", "written")):
        return "email"
    return text


_CITY_PREFIXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:my|the)\s+city\s+(?:is|would\s+be)\s+", re.IGNORECASE),
    re.compile(r"^city\s+is\s+", re.IGNORECASE),
    re.compile(r"^i\s+(?:live|stay|reside)\s+in\s+", re.IGNORECASE),
    re.compile(r"^(?:i\s+am|i'm)\s+from\s+", re.IGNORECASE),
    re.compile(
        r"^(?:please\s+)?(?:record|set|change)\s+(?:my\s+)?city\s+(?:as|to)\s+",
        re.IGNORECASE,
    ),
)


def _normalise_city(value: Any) -> str:
    """Extract a city name from common conversational answer forms."""

    text = _clean_text(value).strip(" \t.,!?;:")
    for prefix in _CITY_PREFIXES:
        stripped = prefix.sub("", text, count=1).strip(" \t.,!?;:")
        if stripped != text:
            text = stripped
            break

    # A caller may include a state for clarity (for example, "Pune,
    # Maharashtra"), but this field deliberately stores only the city.
    text = text.split(",", maxsplit=1)[0].strip(" \t.,!?;:")
    if not text:
        raise ValueError("I could not identify the city.")
    return text.title()


def _validate_amount(value: Decimal) -> None:
    if not Decimal(50000) <= value <= Decimal(200000):
        raise ValueError(
            "The demonstration amount must be between Rs. 50,000 and Rs. 2,00,000."
        )


def _validate_non_negative(value: Decimal) -> None:
    if value < 0:
        raise ValueError("The amount cannot be negative.")


def _validate_income(value: Decimal) -> None:
    if value <= 0:
        raise ValueError("Monthly income must be greater than zero.")


def _validate_tenure(value: int) -> None:
    if value not in {6, 12, 18, 24}:
        raise ValueError("The demonstration tenure must be 6, 12, 18, or 24 months.")


def _validate_employment(value: str) -> None:
    if value not in {"salaried", "self-employed"}:
        raise ValueError("Employment type must be salaried or self-employed.")


def _validate_contact(value: str) -> None:
    if value not in {"phone", "email"}:
        raise ValueError(
            "Contact preference must be phone or email; no contact detail is collected."
        )


def _validate_short_text(value: str) -> None:
    if not 2 <= len(value) <= 80:
        raise ValueError("The answer must contain between 2 and 80 characters.")


FIELD_ORDER: tuple[FieldId, ...] = (
    FieldId.REQUESTED_AMOUNT,
    FieldId.LOAN_PURPOSE,
    FieldId.PREFERRED_TENURE,
    FieldId.EMPLOYMENT_TYPE,
    FieldId.MONTHLY_INCOME,
    FieldId.EXISTING_REPAYMENTS,
    FieldId.CITY,
    FieldId.CONTACT_PREFERENCE,
)


FIELD_DEFINITIONS: dict[FieldId, FieldDefinition] = {
    FieldId.REQUESTED_AMOUNT: FieldDefinition(
        FieldId.REQUESTED_AMOUNT,
        "What loan amount would you like to use for this demonstration draft?",
        _normalise_money,
        _validate_amount,
    ),
    FieldId.LOAN_PURPOSE: FieldDefinition(
        FieldId.LOAN_PURPOSE,
        "What is the purpose of the loan?",
        _clean_text,
        _validate_short_text,
    ),
    FieldId.PREFERRED_TENURE: FieldDefinition(
        FieldId.PREFERRED_TENURE,
        "Which tenure do you prefer: 6, 12, 18, or 24 months?",
        _normalise_tenure,
        _validate_tenure,
    ),
    FieldId.EMPLOYMENT_TYPE: FieldDefinition(
        FieldId.EMPLOYMENT_TYPE,
        "Are you salaried or self-employed?",
        _normalise_employment,
        _validate_employment,
    ),
    FieldId.MONTHLY_INCOME: FieldDefinition(
        FieldId.MONTHLY_INCOME,
        "What is your monthly take-home income for this synthetic draft?",
        _normalise_money,
        _validate_income,
    ),
    FieldId.EXISTING_REPAYMENTS: FieldDefinition(
        FieldId.EXISTING_REPAYMENTS,
        "What are your existing monthly repayments? Say zero if there are none.",
        _normalise_money,
        _validate_non_negative,
    ),
    FieldId.CITY: FieldDefinition(
        FieldId.CITY,
        "Which city should the demonstration draft record?",
        _normalise_city,
        _validate_short_text,
    ),
    FieldId.CONTACT_PREFERENCE: FieldDefinition(
        FieldId.CONTACT_PREFERENCE,
        "Would you prefer a hypothetical follow-up by phone or email? Do not provide the actual detail.",
        _normalise_contact,
        _validate_contact,
    ),
}


def normalise_and_validate(field_id: FieldId, raw_value: Any) -> Any:
    definition = FIELD_DEFINITIONS[field_id]
    try:
        normalized = definition.normalizer(raw_value)
        definition.validator(normalized)
        return normalized
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise FieldValidationError(field_id, "invalid_field_value", str(exc)) from exc


def next_unanswered_field(values: dict[FieldId, Any]) -> FieldId | None:
    return next((field_id for field_id in FIELD_ORDER if field_id not in values), None)
