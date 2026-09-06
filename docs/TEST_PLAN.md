# Test plan

Tests are written now but are intentionally not executed during the development-only session.

## Automated deterministic suite

- TR-1: answer/doubt/mixed/control/ambiguity gating and low-STT-confidence holding.
- TR-2: exact one-field commits, revision conflicts, idempotency, correction confirmation, checkpoints and stale jobs.
- TR-3: approved fact retrieval, abstention, deterministic calculation routing and evidence IDs.
- TR-4: value-label preservation, short speech segmentation and draft disclosures.
- TR-5: stop, pause, resume, repeat, go-back, output clearing and stale generation rejection.
- TR-6: pressure, urgency, recommendation, sensitive-data and forbidden-action red teams.
- System: two-session isolation, trace replay, acceptance verdict logic and the frozen fifteen-scenario manifest.

## Opt-in live tests

Live tests are marked `live` and skipped unless `RUN_LIVE_TESTS=1`. They consume quota and cover:

- Qdrant ingestion plus product/version/status-filtered retrieval.
- Groq strict structured interpretation.
- Later provider checks for Deepgram streaming and Rime synthesis.

## Manual tests

Manual tests remain skipped placeholders until the evaluation session:

- two-listener review of financial value-label intelligibility and pacing;
- live microphone barge-in and end-user stop latency;
- final browser journey and dashboard visual inspection.

## Commands for the later test session

```powershell
uv sync --dev
uv run pytest -m "not live and not manual"
$env:RUN_LIVE_TESTS="1"
uv run pytest -m live
```

Do not commit provider credentials or exported recordings containing real personal information.
