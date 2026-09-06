# Saarthi Voice Loan Assistant

Saarthi is a voice-first, doubt-aware assistant for a **fictional personal-loan pre-application**. It proves that a borrower can answer one field at a time, leave the expected path to ask a question or make a correction, interrupt output, and resume without corrupting the draft.

## Safety boundary

- Synthetic, non-sensitive data only.
- One fictional product and one approved fact-set version.
- The only outcome is a reviewable or cancelled draft.
- There is no submission, approval, rejection, KYC, mandate, payment, or disbursal capability.
- Models propose meaning and wording; deterministic components own mutations, calculations, release gates, cancellation, and allowed actions.

## Repository layout

```text
src/saarthi/
  api/          FastAPI session, token, control, draft and trace routes
  agent/        LiveKit worker and voice turn integration
  domain/       Typed contracts, field rules, reducer and state machine
  providers/    Groq, Deepgram/Rime, Qdrant, Redis and LiveKit adapters
  services/     Interpretation, grounding, calculation, planning and rendering
  storage/      SQLite repositories and append-only trace store
  scripts/      Product-fact ingestion
web/            Borrower and evidence-dashboard UI
data/product/   Versioned synthetic product facts
tests/          Unit, scenario, integration, provider-contract and red-team tests
```

## Local setup

1. Install Python 3.12 and `uv`.
2. Copy `.env.example` to `.env` and fill the provider credentials.
3. Install dependencies with `uv sync --dev`.
4. Ingest the approved facts with `uv run saarthi-ingest`.
5. Start the API with `uv run saarthi-api`.
6. Start the agent worker separately with `uv run saarthi-agent dev`.

The test suite is intentionally separated into deterministic, integration, live-provider, and manual checks. Live tests are opt-in and must never run by accident.
