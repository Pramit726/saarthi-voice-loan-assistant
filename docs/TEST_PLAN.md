# Test plan

This plan defines the repeatable checks for the submission build. During the 8 September 2026 package audit, the deterministic backend suite passed 99 tests with five live/manual tests deselected. The frontend suite passed six tests, the production build completed, and the Rime configuration preflight passed.

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
- Gemini structured interpretation used by the production interpreter.
- Optional Groq structured output for the non-default grounded-wording path.
- Provider checks for Deepgram streaming and Rime synthesis where a live fixture is available.

## Manual tests

These checks require a live browser, microphone, provider connection, or human listener. Their bounded development results are summarized in the MVP design document; rerun the final demo path in the deployed environment before submission:

- two-listener review of financial value-label intelligibility and pacing;
- live microphone barge-in and end-user stop latency;
- final browser journey and dashboard visual inspection.

## Repeatable commands

```powershell
uv sync --dev
uv run pytest -m "not live and not manual"
cd web
npm test -- --run
npm run build
cd ..
uv run saarthi-rime-preflight
$env:RUN_LIVE_TESTS="1"
uv run pytest -m live
```

Do not commit provider credentials or exported recordings containing real personal information.
