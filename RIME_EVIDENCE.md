# Rime evidence

## Hard voice claim

Saarthi preserves critical financial values and their labels when converting an approved response into spoken output. The spoken response is generated from the same structured projection shown in the written draft, is split into listener-oriented segments, and is released only while its generation is current.

## Acceptance test

For paired ordinary-prose and listener-oriented renderings:

- critical value-label agreement must be 100% for the tested facts;
- the spoken output must remain intelligible enough for the bounded review;
- the optimized rendering should not reduce naturalness across the paired samples;
- stale or interrupted speech must not re-enter after a newer generation begins.

## Procedure and fixture

The deterministic regression fixture is:

```powershell
uv run pytest -q tests/test_tr4_financial_speech.py
```

The integrated evaluation used 25 paired utterances, 45 financial facts, 50 Rime outputs, and ASR round trips. It compared ordinary financial prose with the listener-oriented renderer before sending both through the same Rime configuration.

The local configuration and secret preflight is repeatable with:

```powershell
uv run saarthi-rime-preflight
```

The preflight checks presence without printing `RIME_API_KEY` and verifies the exact model, speaker, language, endpoint, transport, and audio settings documented below.

## Result

The listener-oriented rendering preserved 45/45 tested facts, achieved 97.8% ASR fact recall versus 15.6% for the ordinary-prose baseline, and was preferred in 23/25 paired comparisons.

## Reproduction configuration

| Setting | Value |
|---|---|
| Model ID | `coda` |
| Speaker | `nadi` |
| Language | `eng` (fixed English demonstration profile) |
| Endpoint | `wss://users-ws.rime.ai` |
| Transport | WebSocket streaming through `livekit-plugins-rime` |
| Audio | `audio/pcm`, mono, 24,000 Hz |
| Speed | `speedAlpha=0.92` |

## Limitations

The result is a bounded engineering evaluation, not a population-level listening study. The fixtures and financial facts are synthetic, the ASR round trip is a proxy for intelligibility, the paired review used a small internal listener group, and provider/network conditions can change latency or audio quality. The result does not establish regulated lending suitability, accessibility compliance, or production telephony performance.
