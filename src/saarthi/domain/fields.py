from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import geonamescache

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
    text = _clean_text(value).casefold().replace("_", "-")
    self_employed = re.search(
        r"\b(?:self[ -]?employed|business(?: owner)?|entrepreneur|proprietor|"
        r"shopkeeper|freelanc(?:e|er)|consultant|contractor|gig worker|"
        r"independent(?: consultant| consulting| work)?)\b|"
        r"\b(?:own|run|operate|manage)\b.{0,28}\b(?:business|shop|firm|company)\b",
        text,
    )
    salaried = re.search(
        r"\b(?:salaried|salary|employee|payroll|government job|"
        r"private job|office job)\b|\bwork(?:ing)?\b.{0,24}\bfor\b.{0,24}"
        r"\b(?:company|firm|employer|government)\b",
        text,
    )
    if not salaried and not re.search(r"\bself[ -]?employed\b", text):
        salaried = re.search(r"\bemployed\b", text)
    if self_employed and salaried:
        raise ValueError("Please choose salaried or self-employed as the main type.")
    if self_employed:
        return "self-employed"
    if salaried:
        return "salaried"
    return text


_LOAN_PURPOSE_PATTERNS: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = (
    (
        "education",
        (
            re.compile(
                r"\b(?:education|educational|tuition|school|college|university|"
                r"course|coaching|classes|academic fees?|school fees?|college fees?|"
                r"stud(?:y|ies))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "medical expenses",
        (
            re.compile(
                r"\b(?:medical|hospital|surgery|treatment|healthcare|medicine|"
                r"doctor(?:'s)? bills?|medical bills?)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "home renovation",
        (
            re.compile(
                r"\b(?:renovat(?:e|ion|ing)|home improvement|house repairs?|"
                r"home repairs?|house construction|fix(?:ing)?\b.{0,24}"
                r"\b(?:house|home|roof))\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "wedding",
        (re.compile(r"\b(?:wedding|marriage)\b", re.IGNORECASE),),
    ),
    (
        "travel",
        (re.compile(r"\b(?:travel|trip|vacation|holiday)\b", re.IGNORECASE),),
    ),
    (
        "debt consolidation",
        (
            re.compile(
                r"\b(?:debt|consolidat(?:e|ion)|credit card dues?|repay(?:ing|ment)? another loan)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "vehicle purchase",
        (
            re.compile(
                r"\b(?:vehicle|car|bike|motorcycle|scooter)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "business expenses",
        (
            re.compile(
                r"\b(?:business|working capital|inventory|shop expenses?|"
                r"business equipment|equipment for (?:my |the )?shop)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "consumer purchase",
        (
            re.compile(
                r"\b(?:laptop|computer|appliance|electronics?|furniture)\b",
                re.IGNORECASE,
            ),
        ),
    ),
    (
        "personal expenses",
        (
            re.compile(
                r"\b(?:personal|family expenses?|household expenses?|emergency)\b",
                re.IGNORECASE,
            ),
        ),
    ),
)


def _normalise_loan_purpose(value: Any) -> str:
    """Map a meaningful spoken purpose to the bounded demo taxonomy."""

    text = _clean_text(value).strip(" \t.,!?;:")
    if not re.search(r"[a-z]", text, re.IGNORECASE):
        raise ValueError("I could not identify a loan purpose.")

    matches = {
        purpose
        for purpose, patterns in _LOAN_PURPOSE_PATTERNS
        if any(pattern.search(text) for pattern in patterns)
    }
    if len(matches) > 1:
        raise ValueError("Please state one main loan purpose.")
    if not matches:
        raise ValueError(
            "Please give a specific purpose such as education, medical expenses, "
            "home renovation, wedding, travel, debt consolidation, vehicle purchase, "
            "business expenses, or personal expenses."
        )
    return matches.pop()


def _normalise_contact(value: Any) -> str:
    text = _clean_text(value).casefold()
    phone = bool(re.search(r"\b(?:call|phone|telephone|voice)\b", text))
    email = bool(
        re.search(
            r"\b(?:e[ -]?mail|mail|gmail|written(?: message| follow-up)?)\b", text
        )
    )
    if phone and email:
        raise ValueError("Please choose only one contact preference: phone or email.")
    if phone:
        return "phone"
    if email:
        return "email"
    raise ValueError("Contact preference must explicitly say phone or email.")


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


def _city_key(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value.casefold())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return " ".join(re.findall(r"[a-z]+", ascii_value))


_MANUAL_CITY_ALIASES: dict[str, str] = {
    "allahabad": "Prayagraj",
    "bangalore": "Bengaluru",
    # Frequent Indian-English and ASR renderings observed in manual tests.
    "bangalor": "Bengaluru",
    "bangaluru": "Bengaluru",
    "banglore": "Bengaluru",
    "bangluru": "Bengaluru",
    "bengaluru city": "Bengaluru",
    "benglore": "Bengaluru",
    "bengluru": "Bengaluru",
    "bingaluru": "Bengaluru",
    "bingloru": "Bengaluru",
    "bombay": "Mumbai",
    "calcutta": "Kolkata",
    "cochin": "Kochi",
    "gurgaon": "Gurugram",
    "madras": "Chennai",
    "mangalore": "Mangaluru",
    "mysore": "Mysuru",
    "poona": "Pune",
    "poonah": "Pune",
    "pooning": "Pune",
    "poooning": "Pune",
    "puna": "Pune",
    "trichy": "Tiruchirappalli",
    "trivandrum": "Thiruvananthapuram",
    "vizag": "Visakhapatnam",
}


@dataclass(frozen=True)
class CitySuggestion:
    city: str
    score: float
    source: str = "geonames_offline"


@lru_cache(maxsize=1)
def _indian_city_aliases() -> dict[str, frozenset[str]]:
    """Load canonical and alternate Indian city names from GeoNames once."""

    aliases: dict[str, set[str]] = {}
    cities = geonamescache.GeonamesCache().get_cities().values()
    for record in cities:
        if record.get("countrycode") != "IN":
            continue
        canonical = str(record.get("name", "")).strip()
        if not canonical:
            continue
        names = [canonical, *record.get("alternatenames", [])]
        for name in names:
            key = _city_key(str(name))
            if len(key) >= 2:
                aliases.setdefault(key, set()).add(canonical)

    # Product-tested aliases deliberately override historical or ambiguous
    # GeoNames alternatives while still resolving to a canonical city value.
    for alias, canonical in _MANUAL_CITY_ALIASES.items():
        aliases[alias] = {canonical}
    return {key: frozenset(values) for key, values in aliases.items()}


def _extract_city_text(value: Any) -> str:
    text = _clean_text(value).strip(" \t.,!?;:")
    for prefix in _CITY_PREFIXES:
        stripped = prefix.sub("", text, count=1).strip(" \t.,!?;:")
        if stripped != text:
            text = stripped
            break

    # A caller may include a state for clarity (for example, "Pune,
    # Maharashtra"), but this field deliberately stores only the city.
    text = text.split(",", maxsplit=1)[0].strip(" \t.,!?;:")
    text = re.sub(
        r"\s+(?:full|please|only|actually|thanks?)$", "", text, flags=re.IGNORECASE
    )
    return text


def _resolve_city_exact(text: str) -> str:
    key = _city_key(text)
    if not key:
        raise ValueError("I could not identify the city.")
    if re.search(r"\b(?:or|and)\b", key):
        raise ValueError("I heard more than one city. Please say one city name.")

    candidates = _indian_city_aliases().get(key, frozenset())
    if len(candidates) == 1:
        return next(iter(candidates))
    if len(candidates) > 1:
        canonical_matches = {
            candidate for candidate in candidates if _city_key(candidate) == key
        }
        if len(canonical_matches) == 1:
            return next(iter(canonical_matches))
        ascii_matches = {
            candidate
            for candidate in canonical_matches
            if candidate.isascii() and candidate.casefold() == key
        }
        if len(ascii_matches) == 1:
            return next(iter(ascii_matches))
        raise ValueError(
            "That city name is ambiguous. Please also say the state or use a nearby major city."
        )
    raise ValueError("I could not find that Indian city in the local GeoNames index.")


def suggest_indian_city(value: Any) -> CitySuggestion | None:
    """Return one conservative fuzzy GeoNames candidate for explicit confirmation."""

    key = _city_key(_extract_city_text(value))
    if len(key) < 3 or re.search(r"\b(?:or|and)\b", key):
        return None

    scores: dict[str, float] = {}
    for alias, canonical_names in _indian_city_aliases().items():
        if alias[0] != key[0] or abs(len(alias) - len(key)) > 3:
            continue
        score = SequenceMatcher(None, key, alias).ratio()
        for canonical in canonical_names:
            scores[canonical] = max(score, scores.get(canonical, 0.0))
    if len(scores) < 2:
        return None

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_city, best_score = ranked[0]
    second_score = ranked[1][1]
    if best_score >= 0.84 and best_score - second_score >= 0.04:
        return CitySuggestion(city=best_city, score=best_score)
    return None


def _normalise_city(value: Any) -> str:
    """Validate an exact city/alias against the offline Indian GeoNames index."""

    return _resolve_city_exact(_extract_city_text(value))


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
        "What is the main purpose of the loan, such as education, medical expenses, home renovation, travel, or another personal expense?",
        _normalise_loan_purpose,
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
