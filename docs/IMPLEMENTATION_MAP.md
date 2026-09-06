# Implementation map

This file maps the refined design to code without widening the product scope.

| Requirement | Primary implementation | Deterministic boundary |
|---|---|---|
| TR-1 Off-path understanding | `services/interpreter.py`, `providers/groq.py` | The interpreter returns a typed proposal. Doubts, controls, ambiguity and mixed turns cannot authorize writes. |
| TR-2 State consistency | `domain/state.py`, `domain/reducer.py`, `storage/` | Three independent versions, compare-and-set revision, idempotency and explicit correction confirmation. |
| TR-3 Grounded explanation | `providers/knowledge.py`, `providers/cache.py`, `services/grounding.py` | Product/version/status filters, fact IDs, deterministic calculation route and abstention. |
| TR-4 Financial speech | `services/calculator.py`, `services/renderer.py`, LiveKit Rime adapter | Speech and written output are derived from the same typed projection and value-label map. |
| TR-5 Control and cancellation | `domain/state.py`, `services/orchestrator.py`, `agent/worker.py` | New generation first, local speech interruption, old-job cancellation and current-version checks. |
| TR-6 Neutral draft-only behavior | `domain/policies.py`, `services/planner.py`, API surface | Deterministic release gates and an allowlist; forbidden lending actions have no route or handler. |

## Runtime processes

1. The React borrower UI creates an anonymous session and requests a room-scoped LiveKit token.
2. The LiveKit worker receives Deepgram final transcripts and sends each one through `TurnOrchestrator`.
3. The orchestrator loads authoritative state, establishes a new generation, asks TR-1 for a typed proposal, and routes it.
4. Only `GuardedReducer` can produce a committed draft revision.
5. Product questions use the cached `KnowledgeProvider`; Qdrant is primary and the same approved local fact artifact is the bounded fallback.
6. TR-6 evaluates the plan before `ListenerRenderer` creates Rime-ready segments.
7. Every material decision is appended to the trace used by the dashboard and replay service.

## Deliberate differences from FieldMate

- Saarthi does not release speculative LLM speech while grounding is still unresolved.
- The vector database holds approved versioned product facts, not user memory.
- Redis is a disposable exact retrieval cache and never stores personalized audio.
- Application fields are committed only through an atomic reducer transaction.
- Submission, approval, KYC, mandate, payment and disbursal capabilities do not exist.
