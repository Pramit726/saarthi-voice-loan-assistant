# Rime evidence

## Selected hard voice claim

Saarthi's selected hard voice problem is **full-duplex interruption and recovery with transactional state consistency**. While Rime speech or a product lookup is active, a newer finalized user turn or control command establishes a new generation before replacement work begins. Audio and model/tool results from the older generation must not re-enter the conversation or mutate the application. A doubt must preserve the exact pending-field checkpoint, and a correction must change only its explicitly confirmed target.

Rime is the primary spoken-output provider in this path. Interruption safety is a property of the complete application--LiveKit transport, local playback control, generation fencing, the guarded reducer, and Rime streaming--not a claim about the TTS model alone.

## Acceptance test

Run one normal field-answer interaction and the following deliberate stress case:

1. Begin a Rime response or a deliberately delayed product-fact lookup while a form field is pending.
2. Before that work finishes, issue a new user turn, `stop`, `pause`, or a correction.
3. Verify that the generation advances before replacement work is released and queued playback is cleared or stopped.
4. Release the delayed old result and verify that it produces no speech and no application mutation.
5. For a doubt, verify that the application revision does not change and the exact pending field is restored.
6. For a confirmed correction, verify that only the intended field changes and that the interrupted checkpoint remains resumable.

The release gates are:

- zero obsolete model/tool results or queued audio re-entering after a newer generation;
- zero unintended or silent field mutations;
- exact pending-field preservation and resumption in every scripted scenario;
- controls never being stored as field answers; and
- user-facing stop latency target of p95 at or below 500 ms in the shipped browser/audio path.

Any stale re-entry or unintended mutation is a failure, not an averaged metric. Missing live evidence is reported as inconclusive rather than treated as a pass.

## Repeatable procedure and fixtures

Run the deterministic interruption, state, cancellation, delayed-result, and financial-speech fixtures:

```powershell
uv run pytest -q tests/test_tr2_state_machine.py tests/test_tr2_reducer.py tests/test_tr5_controls.py tests/test_orchestrator_failure_recovery.py tests/test_tr4_financial_speech.py
```

These fixtures verify exact checkpoint restoration, one-field commits, revision conflicts, confirmation-gated corrections, generation invalidation, active-job cancellation, queued-audio clearing, heard-versus-unheard speech history, and rejection of a delayed grounding result after a newer turn starts.

Before a live run, verify the exact Rime configuration without printing the secret:

```powershell
uv run saarthi-rime-preflight
```

For the shipped-path check, start the API, LiveKit worker, and web client; perform the stress case above; then inspect the selected session in the evidence dashboard or retrieve:

```text
GET /api/sessions/{session_id}/events
GET /api/sessions/{session_id}/acceptance
```

The trace should show the accepted turn or control, its generation boundary, unchanged or intentionally advanced application revision, checkpoint, cancelled or blocked stale work, and the final released/delivered Rime segment.

## Results

### Primary result: interruption and state consistency

- **Current deterministic regression:** 25/25 relevant TR-2, TR-5, delayed-result, and TR-4 tests passed.
- **TR-2 bounded evaluation:** 30 scripted conversations and 71 state transitions per approach. The guarded reducer achieved 100% of the defined scenario/state checks with zero unintended mutations.
- **TR-5 bounded evaluation:** 12 cancellation and delayed-result integration scenarios all passed, with no obsolete result or audio re-entry.
- **Controlled stop measurement:** four trials using real Rime PCM and a virtual sink produced 17.5 ms application-side stop p95.

The 17.5 ms value measures the application cancellation path; it is not presented as end-to-end acoustic or browser stop latency. The browser-to-audible-stop target remains p95 at or below 500 ms and must be remeasured in the final deployment environment.

### Secondary result: faithful Rime financial speech

The listener-oriented renderer was evaluated on 25 paired utterances containing 45 financial facts and 50 Rime outputs. It preserved 45/45 tested facts, achieved 97.8% ASR fact recall versus 15.6% for the ordinary-prose baseline, and was preferred in 23/25 bounded paired reviews. This supports delivery quality, but it is secondary to the selected interruption-and-recovery claim.

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

The scripted conversations, product facts, and state transitions are synthetic. The deterministic suite proves application invariants but does not reproduce network jitter, microphone echo, device buffering, or every LiveKit/Rime timing condition. The 17.5 ms stop result is an application-side controlled measurement with only four trials, not an end-to-end user-perceived latency result. The ASR round trip is a proxy for intelligibility, and the paired speech review used a small internal group. Provider and network conditions can change latency and audio quality. These results do not establish regulated lending suitability, accessibility compliance, population-level comprehension, or production telephony performance.
