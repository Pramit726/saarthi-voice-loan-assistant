from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request

from saarthi.api.schemas import (
    ControlRequest,
    DeliveryUpdate,
    SessionCreateResponse,
    TextTurnRequest,
    TokenRequest,
    TokenResponse,
)
from saarthi.domain.contracts import FinalTranscript, new_id, utc_now
from saarthi.domain.enums import DeliveryStatus
from saarthi.domain.fields import FIELD_DEFINITIONS
from saarthi.domain.state import ConversationStateMachine
from saarthi.runtime import Runtime

router = APIRouter(prefix="/api")


def runtime_from(request: Request) -> Runtime:
    return request.app.state.runtime


@router.get("/health")
async def health(request: Request) -> dict:
    runtime = runtime_from(request)
    return {
        "status": "ok",
        "service": runtime.settings.app_name,
        "environment": runtime.settings.environment,
        "missing_provider_configuration": runtime.settings.missing_required_providers(),
        "product_id": "SPL-DEMO-01",
        "product_version": "1.1",
    }


@router.post("/sessions", response_model=SessionCreateResponse, status_code=201)
async def create_session(request: Request) -> SessionCreateResponse:
    runtime = runtime_from(request)
    draft, state = await runtime.sessions.create()
    room_name = f"saarthi-{state.session_id}"
    opening = state.last_safe_prompt or FIELD_DEFINITIONS[state.pending_field].prompt
    return SessionCreateResponse(
        session_id=state.session_id,
        application_id=draft.application_id,
        participant_id=state.participant_id,
        trace_id=state.trace_id,
        room_name=room_name,
        pending_field=state.pending_field.value if state.pending_field else None,
        opening_prompt=opening,
    )


@router.post("/livekit/token", response_model=TokenResponse)
async def create_livekit_token(
    payload: TokenRequest, request: Request
) -> TokenResponse:
    runtime = runtime_from(request)
    state = await runtime.repository.get_state(payload.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    room_name = f"saarthi-{state.session_id}"
    token = runtime.livekit_tokens.issue(
        room=room_name,
        participant_identity=state.participant_id,
        participant_name="Synthetic borrower",
    )
    try:
        await runtime.livekit_tokens.dispatch_agent(
            room=room_name,
            agent_name=runtime.settings.livekit_agent_name,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not dispatch voice worker: {type(exc).__name__}",
        ) from exc
    return TokenResponse(
        url=runtime.settings.livekit_url,
        token=token,
        room_name=room_name,
        participant_identity=state.participant_id,
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request) -> dict:
    runtime = runtime_from(request)
    state = await runtime.repository.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.model_dump(mode="json")


@router.get("/sessions/{session_id}/draft")
async def get_draft(session_id: str, request: Request) -> dict:
    runtime = runtime_from(request)
    state = await runtime.repository.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    draft = await runtime.repository.get_draft(state.application_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft.model_dump(mode="json")


@router.get("/sessions/{session_id}/events")
async def get_events(session_id: str, request: Request) -> list[dict]:
    runtime = runtime_from(request)
    if await runtime.repository.get_state(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    events = await runtime.repository.list_events(session_id)
    return [event.model_dump(mode="json") for event in events]


@router.get("/sessions/{session_id}/acceptance")
async def get_acceptance(session_id: str, request: Request) -> dict:
    runtime = runtime_from(request)
    events = await runtime.repository.list_events(session_id)
    if not events:
        raise HTTPException(status_code=404, detail="Session or evidence not found")
    return runtime.acceptance.evaluate(events).model_dump(mode="json")


@router.post("/sessions/{session_id}/turns")
async def process_text_turn(
    session_id: str, payload: TextTurnRequest, request: Request
) -> dict:
    """Development and transcript-level test entrypoint; voice uses the same orchestrator."""

    runtime = runtime_from(request)
    state = await runtime.repository.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    now = utc_now()
    transcript = FinalTranscript(
        session_id=session_id,
        participant_id=state.participant_id,
        turn_id=new_id("turn"),
        generation_id=state.generation_id + 1,
        text=payload.text,
        language=payload.language,
        confidence=payload.confidence,
        started_at=now - timedelta(milliseconds=250),
        ended_at=now,
    )
    outcome = await runtime.orchestrator.process_final_transcript(transcript)
    return outcome.model_dump(mode="json")


@router.post("/sessions/{session_id}/controls")
async def apply_control(
    session_id: str, payload: ControlRequest, request: Request
) -> dict:
    command_text = {
        "go_back": "go back",
        "show_summary": "show my summary",
    }.get(payload.command.value, payload.command.value)
    return await process_text_turn(
        session_id, TextTurnRequest(text=command_text), request
    )


@router.post("/sessions/{session_id}/delivery")
async def update_delivery(
    session_id: str, payload: DeliveryUpdate, request: Request
) -> dict:
    runtime = runtime_from(request)
    state = await runtime.repository.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if payload.status is DeliveryStatus.DELIVERED:
        state = ConversationStateMachine.mark_segment_delivered(
            state, payload.segment_id
        )
    else:
        found = False
        for segment in state.output_queue:
            if segment.segment_id == payload.segment_id:
                segment.delivery_status = payload.status
                segment.heard_character_count = min(
                    payload.heard_character_count, len(segment.text)
                )
                found = True
        if not found:
            raise HTTPException(status_code=404, detail="Speech segment not found")
    await runtime.repository.save_state(state)
    return {
        "updated": True,
        "segment_id": payload.segment_id,
        "status": payload.status.value,
    }


@router.get("/sessions/{session_id}/export")
async def export_draft(session_id: str, request: Request) -> dict:
    runtime = runtime_from(request)
    state = await runtime.repository.get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    draft = await runtime.repository.get_draft(state.application_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {
        "label": "Draft for review - not submitted",
        "synthetic": True,
        "application": draft.model_dump(mode="json"),
        "approved_fact_sheet": {
            "product_id": draft.product_id,
            "product_version": draft.product_version,
        },
    }
