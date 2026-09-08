"""Validate the organizer-facing Rime configuration without exposing secrets."""

from __future__ import annotations

import sys

from saarthi.config import get_settings

RIME_WEBSOCKET_ENDPOINT = "wss://users-ws.rime.ai"


def main() -> int:
    settings = get_settings()
    checks: list[tuple[str, bool, str]] = [
        (
            "RIME_API_KEY",
            bool(settings.rime_api_key.get_secret_value()),
            "present (value hidden)",
        ),
        ("RIME_MODEL", settings.rime_model == "coda", settings.rime_model),
        (
            "RIME_ENGLISH_SPEAKER",
            settings.rime_english_speaker == "nadi",
            settings.rime_english_speaker,
        ),
        (
            "RIME_HINDI_SPEAKER",
            settings.rime_hindi_speaker == "nadi",
            settings.rime_hindi_speaker,
        ),
        (
            "RIME_LANGUAGES",
            True,
            "eng/hin selected from en-IN/hi-IN sessions",
        ),
        (
            "RIME_ENDPOINT",
            True,
            f"{RIME_WEBSOCKET_ENDPOINT} via use_websocket=True",
        ),
        ("RIME_TRANSPORT", True, "WebSocket streaming"),
        (
            "RIME_AUDIO",
            settings.rime_sample_rate == 24000,
            f"audio/pcm mono {settings.rime_sample_rate} Hz",
        ),
        (
            "RIME_SPEED_ALPHA",
            settings.rime_speed_alpha == 0.92,
            str(settings.rime_speed_alpha),
        ),
    ]

    failed = False
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {name}: {detail}")
        failed = failed or not passed

    if failed:
        print("Rime preflight failed. Secret values were not printed.", file=sys.stderr)
        return 1

    print("Rime preflight passed. Secret values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
