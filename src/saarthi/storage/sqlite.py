from __future__ import annotations

import json

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from saarthi.domain.contracts import (
    ApplicationDraft,
    ApplicationPatch,
    CommitResult,
    ConversationState,
    FinancialProjection,
    TraceEvent,
    utc_now,
)
from saarthi.domain.reducer import GuardedReducer
from saarthi.domain.enums import DraftStatus


metadata = MetaData()

sessions = Table(
    "sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("application_id", String, unique=True, nullable=False),
    Column("state_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

applications = Table(
    "application_drafts",
    metadata,
    Column("application_id", String, primary_key=True),
    Column("owner_session_id", String, unique=True, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

idempotency = Table(
    "idempotency_results",
    metadata,
    Column("idempotency_key", String, primary_key=True),
    Column("application_id", String, nullable=False),
    Column("result_payload", Text, nullable=False),
)

trace_events = Table(
    "trace_events",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String, unique=True, nullable=False),
    Column("session_id", String, index=True, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)


def _dump(model) -> str:
    return json.dumps(model.model_dump(mode="json"), separators=(",", ":"))


class SqliteStateRepository:
    def __init__(self, database_url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(database_url)

    async def initialize(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def create(self, draft: ApplicationDraft, state: ConversationState) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                insert(applications).values(
                    application_id=draft.application_id,
                    owner_session_id=draft.owner_session_id,
                    revision=draft.revision,
                    payload=_dump(draft),
                    updated_at=draft.updated_at,
                )
            )
            await connection.execute(
                insert(sessions).values(
                    session_id=state.session_id,
                    application_id=state.application_id,
                    state_version=state.state_version,
                    payload=_dump(state),
                    updated_at=state.updated_at,
                )
            )

    async def get_draft(self, application_id: str) -> ApplicationDraft | None:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    select(applications.c.payload).where(applications.c.application_id == application_id)
                )
            ).first()
        return ApplicationDraft.model_validate_json(row.payload) if row else None

    async def get_state(self, session_id: str) -> ConversationState | None:
        async with self.engine.connect() as connection:
            row = (
                await connection.execute(
                    select(sessions.c.payload).where(sessions.c.session_id == session_id)
                )
            ).first()
        return ConversationState.model_validate_json(row.payload) if row else None

    async def save_state(self, state: ConversationState) -> None:
        async with self.engine.begin() as connection:
            result = await connection.execute(
                update(sessions)
                .where(sessions.c.session_id == state.session_id)
                .values(
                    state_version=state.state_version,
                    payload=_dump(state),
                    updated_at=state.updated_at,
                )
            )
            if result.rowcount != 1:
                raise KeyError(state.session_id)

    async def cancel_draft(self, application_id: str, session_id: str) -> ApplicationDraft:
        async with self.engine.begin() as connection:
            row = (
                await connection.execute(
                    select(applications.c.payload).where(
                        applications.c.application_id == application_id,
                        applications.c.owner_session_id == session_id,
                    )
                )
            ).first()
            if not row:
                raise PermissionError("application_or_session_mismatch")
            draft = ApplicationDraft.model_validate_json(row.payload)
            draft.status = DraftStatus.CANCELLED
            draft.updated_at = utc_now()
            await connection.execute(
                update(applications)
                .where(applications.c.application_id == application_id)
                .values(payload=_dump(draft), updated_at=draft.updated_at)
            )
            return draft

    async def attach_projection(
        self, application_id: str, expected_revision: int, projection: FinancialProjection
    ) -> ApplicationDraft:
        async with self.engine.begin() as connection:
            row = (
                await connection.execute(
                    select(applications.c.payload).where(
                        applications.c.application_id == application_id,
                        applications.c.revision == expected_revision,
                    )
                )
            ).first()
            if not row or projection.source_application_revision != expected_revision:
                raise ValueError("stale_projection")
            draft = ApplicationDraft.model_validate_json(row.payload)
            draft.current_projection = projection
            write = await connection.execute(
                update(applications)
                .where(
                    applications.c.application_id == application_id,
                    applications.c.revision == expected_revision,
                )
                .values(payload=_dump(draft), updated_at=utc_now())
            )
            if write.rowcount != 1:
                raise ValueError("stale_projection")
            return draft

    async def commit_patch(
        self,
        patch: ApplicationPatch,
        *,
        current_generation_id: int,
        reducer: GuardedReducer,
    ) -> CommitResult:
        async with self.engine.begin() as connection:
            prior = (
                await connection.execute(
                    select(idempotency.c.result_payload).where(
                        idempotency.c.idempotency_key == patch.idempotency_key
                    )
                )
            ).first()
            if prior:
                return CommitResult.model_validate_json(prior.result_payload)

            row = (
                await connection.execute(
                    select(applications.c.payload).where(
                        applications.c.application_id == patch.application_id
                    )
                )
            ).first()
            if not row:
                return CommitResult(
                    accepted=False,
                    reason_code="application_not_found",
                    previous_revision=patch.expected_application_revision,
                    new_revision=patch.expected_application_revision,
                )
            draft = ApplicationDraft.model_validate_json(row.payload)
            result = reducer.apply(
                draft,
                patch,
                current_generation_id=current_generation_id,
            )
            if result.accepted and result.draft:
                write = await connection.execute(
                    update(applications)
                    .where(
                        applications.c.application_id == patch.application_id,
                        applications.c.revision == patch.expected_application_revision,
                    )
                    .values(
                        revision=result.new_revision,
                        payload=_dump(result.draft),
                        updated_at=result.draft.updated_at,
                    )
                )
                if write.rowcount != 1:
                    result = CommitResult(
                        accepted=False,
                        reason_code="application_revision_conflict",
                        previous_revision=patch.expected_application_revision,
                        new_revision=patch.expected_application_revision,
                    )
            await connection.execute(
                insert(idempotency).values(
                    idempotency_key=patch.idempotency_key,
                    application_id=patch.application_id,
                    result_payload=_dump(result),
                )
            )
            return result

    async def append_event(self, event: TraceEvent) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(
                insert(trace_events).values(
                    event_id=event.event_id,
                    session_id=event.session_id,
                    occurred_at=event.occurred_at,
                    payload=_dump(event),
                )
            )

    async def list_events(self, session_id: str) -> list[TraceEvent]:
        async with self.engine.connect() as connection:
            rows = (
                await connection.execute(
                    select(trace_events.c.payload)
                    .where(trace_events.c.session_id == session_id)
                    .order_by(trace_events.c.sequence)
                )
            ).all()
        return [TraceEvent.model_validate_json(row.payload) for row in rows]
