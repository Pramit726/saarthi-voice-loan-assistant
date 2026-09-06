from __future__ import annotations

from saarthi.domain.contracts import ApplicationDraft, ConversationState, TraceEvent, new_id
from saarthi.domain.fields import FIELD_DEFINITIONS
from saarthi.domain.enums import FieldId
from saarthi.storage.repository import StateRepository


class SessionService:
    def __init__(self, repository: StateRepository) -> None:
        self.repository = repository

    async def create(self) -> tuple[ApplicationDraft, ConversationState]:
        session_id = new_id("session")
        application_id = new_id("application")
        participant_id = new_id("borrower")
        draft = ApplicationDraft(application_id=application_id, owner_session_id=session_id)
        state = ConversationState(
            session_id=session_id,
            application_id=application_id,
            participant_id=participant_id,
            last_safe_prompt=FIELD_DEFINITIONS[FieldId.REQUESTED_AMOUNT].prompt,
        )
        await self.repository.create(draft, state)
        await self.repository.append_event(
            TraceEvent(
                event_type="session_created",
                session_id=session_id,
                application_id=application_id,
                trace_id=state.trace_id,
                component="session_service",
                outcome="created",
                generation_id=state.generation_id,
                application_revision=draft.revision,
                state_version=state.state_version,
                payload={"synthetic": True, "draft_only": True},
            )
        )
        return draft, state
