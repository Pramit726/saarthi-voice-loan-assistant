from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from saarthi.domain.contracts import (
    ApplicationDraft,
    ApplicationPatch,
    CommitResult,
    ConversationState,
    FinancialProjection,
    TraceEvent,
)
from saarthi.domain.reducer import GuardedReducer


class StateRepository(Protocol):
    async def initialize(self) -> None: ...
    async def create(
        self, draft: ApplicationDraft, state: ConversationState
    ) -> None: ...
    async def get_draft(self, application_id: str) -> ApplicationDraft | None: ...
    async def get_state(self, session_id: str) -> ConversationState | None: ...
    async def save_state(self, state: ConversationState) -> None: ...
    async def cancel_draft(
        self, application_id: str, session_id: str
    ) -> ApplicationDraft: ...
    async def attach_projection(
        self,
        application_id: str,
        expected_revision: int,
        projection: FinancialProjection,
    ) -> ApplicationDraft: ...
    async def commit_patch(
        self,
        patch: ApplicationPatch,
        *,
        current_generation_id: int,
        reducer: GuardedReducer,
    ) -> CommitResult: ...
    async def append_event(self, event: TraceEvent) -> None: ...
    async def list_events(self, session_id: str) -> list[TraceEvent]: ...


class InMemoryStateRepository:
    """Deterministic repository used by unit/scenario tests and offline demos."""

    def __init__(self) -> None:
        self.drafts: dict[str, ApplicationDraft] = {}
        self.states: dict[str, ConversationState] = {}
        self.events: dict[str, list[TraceEvent]] = {}
        self.idempotency_results: dict[str, CommitResult] = {}

    async def initialize(self) -> None:
        return None

    async def create(self, draft: ApplicationDraft, state: ConversationState) -> None:
        if draft.application_id in self.drafts or state.session_id in self.states:
            raise ValueError("Session or application already exists.")
        self.drafts[draft.application_id] = deepcopy(draft)
        self.states[state.session_id] = deepcopy(state)
        self.events[state.session_id] = []

    async def get_draft(self, application_id: str) -> ApplicationDraft | None:
        draft = self.drafts.get(application_id)
        return deepcopy(draft) if draft else None

    async def get_state(self, session_id: str) -> ConversationState | None:
        state = self.states.get(session_id)
        return deepcopy(state) if state else None

    async def save_state(self, state: ConversationState) -> None:
        if state.session_id not in self.states:
            raise KeyError(state.session_id)
        self.states[state.session_id] = deepcopy(state)

    async def cancel_draft(
        self, application_id: str, session_id: str
    ) -> ApplicationDraft:
        draft = self.drafts[application_id]
        if draft.owner_session_id != session_id:
            raise PermissionError("session_mismatch")
        from saarthi.domain.contracts import utc_now
        from saarthi.domain.enums import DraftStatus

        draft.status = DraftStatus.CANCELLED
        draft.updated_at = utc_now()
        self.drafts[application_id] = deepcopy(draft)
        return deepcopy(draft)

    async def attach_projection(
        self,
        application_id: str,
        expected_revision: int,
        projection: FinancialProjection,
    ) -> ApplicationDraft:
        draft = self.drafts[application_id]
        if (
            draft.revision != expected_revision
            or projection.source_application_revision != expected_revision
        ):
            raise ValueError("stale_projection")
        draft.current_projection = projection.model_copy(deep=True)
        self.drafts[application_id] = deepcopy(draft)
        return deepcopy(draft)

    async def commit_patch(
        self,
        patch: ApplicationPatch,
        *,
        current_generation_id: int,
        reducer: GuardedReducer,
    ) -> CommitResult:
        if patch.idempotency_key in self.idempotency_results:
            return deepcopy(self.idempotency_results[patch.idempotency_key])
        draft = self.drafts.get(patch.application_id)
        if draft is None:
            return CommitResult(
                accepted=False,
                reason_code="application_not_found",
                previous_revision=patch.expected_application_revision,
                new_revision=patch.expected_application_revision,
            )
        result = reducer.apply(
            draft,
            patch,
            current_generation_id=current_generation_id,
            seen_idempotency_keys=set(self.idempotency_results),
        )
        if result.accepted and result.draft:
            self.drafts[patch.application_id] = deepcopy(result.draft)
        self.idempotency_results[patch.idempotency_key] = deepcopy(result)
        return result

    async def append_event(self, event: TraceEvent) -> None:
        self.events.setdefault(event.session_id, []).append(deepcopy(event))

    async def list_events(self, session_id: str) -> list[TraceEvent]:
        return deepcopy(self.events.get(session_id, []))
