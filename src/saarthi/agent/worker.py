from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import timedelta
from typing import Any, AsyncIterable

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, TurnHandlingOptions, cli
from livekit.plugins import deepgram, rime

from saarthi.config import get_settings
from saarthi.domain.contracts import FinalTranscript, TraceEvent, new_id, utc_now
from saarthi.domain.enums import DeliveryStatus
from saarthi.runtime import build_runtime


logger = logging.getLogger("saarthi.voice")
settings = get_settings()
server = AgentServer()


class ActiveGeneration:
    def __init__(self) -> None:
        self.sequence = 0
        self.task: asyncio.Task | None = None
        self.speech: Any = None
        self._lock = asyncio.Lock()

    async def begin(self) -> int:
        current = asyncio.current_task()
        async with self._lock:
            self.sequence += 1
            sequence = self.sequence
            previous = self.task
            self.task = current
        if previous and previous is not current and not previous.done():
            previous.cancel()
            with suppress(asyncio.CancelledError):
                await previous
        return sequence

    def is_current(self, sequence: int) -> bool:
        return sequence == self.sequence

    def interrupt(self) -> None:
        self.sequence += 1
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None
        if self.speech is not None and not getattr(self.speech, "interrupted", False):
            with suppress(Exception):
                self.speech.interrupt(force=True)
        self.speech = None


class SaarthiAgent(Agent):
    def __init__(self, opening_prompt: str) -> None:
        super().__init__(
            instructions=(
                "You are only the transport shell for Saarthi. Application responses are created "
                "by the guarded backend, not by LiveKit's default LLM pipeline."
            ),
            allow_interruptions=True,
        )
        self.opening_prompt = opening_prompt

    async def on_enter(self) -> None:
        await self.session.say(
            "Welcome to Saarthi. This is a fictional demonstration and creates only a draft. "
            + self.opening_prompt,
            allow_interruptions=True,
        )


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def entrypoint(ctx: JobContext) -> None:
    runtime = build_runtime(settings)
    await runtime.initialize()
    room_name = ctx.room.name
    session_id = room_name.removeprefix("saarthi-")
    state = await runtime.repository.get_state(session_id)
    if state is None:
        await runtime.close()
        raise RuntimeError(f"No Saarthi session exists for room {room_name}.")

    stt = deepgram.STTv2(model=settings.deepgram_model)
    tts = rime.TTS(
        model=settings.rime_model,
        speaker=settings.rime_speaker,
        sample_rate=settings.rime_sample_rate,
        use_websocket=True,
    )
    voice_session = AgentSession(
        stt=stt,
        tts=tts,
        turn_handling=TurnHandlingOptions(
            turn_detection="stt",
            interruption={
                "enabled": True,
                "mode": "vad",
                "min_duration": 0.15,
                "min_words": 0,
                "false_interruption_timeout": 1.0,
                "resume_false_interruption": True,
                "discard_audio_if_uninterruptible": True,
            },
            preemptive_generation={"enabled": False},
        ),
        min_consecutive_speech_delay=0.0,
    )
    active = ActiveGeneration()

    async def process_final_turn(text: str) -> None:
        local_generation = await active.begin()
        latest = await runtime.repository.get_state(session_id)
        if latest is None:
            return
        now = utc_now()
        transcript = FinalTranscript(
            session_id=session_id,
            participant_id=latest.participant_id,
            turn_id=new_id("turn"),
            generation_id=latest.generation_id + 1,
            text=text,
            confidence=None,
            started_at=now - timedelta(milliseconds=250),
            ended_at=now,
        )
        outcome = await runtime.orchestrator.process_final_transcript(transcript)
        if not active.is_current(local_generation):
            return

        async def response_stream() -> AsyncIterable[str]:
            for segment in outcome.speech_segments:
                current = await runtime.repository.get_state(session_id)
                if (
                    not active.is_current(local_generation)
                    or current is None
                    or current.generation_id != outcome.state.generation_id
                ):
                    return
                yield segment.text

        if not outcome.speech_segments:
            return
        handle = voice_session.say(response_stream(), allow_interruptions=False)
        active.speech = handle
        try:
            await handle
            interrupted = bool(getattr(handle, "interrupted", False))
            current = await runtime.repository.get_state(session_id)
            if current is None:
                return
            for segment in current.output_queue:
                if segment.response_id == outcome.response_plan.response_id:
                    segment.delivery_status = (
                        DeliveryStatus.INTERRUPTED if interrupted else DeliveryStatus.DELIVERED
                    )
                    segment.heard_character_count = 0 if interrupted else len(segment.text)
            if not interrupted:
                current.last_fully_heard_response = [
                    item.model_copy(deep=True)
                    for item in current.output_queue
                    if item.response_id == outcome.response_plan.response_id
                ]
            await runtime.repository.save_state(current)
            await runtime.repository.append_event(
                TraceEvent(
                    event_type="speech_interrupted" if interrupted else "speech_delivered",
                    session_id=current.session_id,
                    application_id=current.application_id,
                    trace_id=current.trace_id,
                    component="livekit_voice_worker",
                    outcome="interrupted" if interrupted else "delivered",
                    turn_id=current.current_turn_id,
                    generation_id=current.generation_id,
                    application_revision=current.linked_application_revision,
                    state_version=current.state_version,
                    payload={"response_id": outcome.response_plan.response_id},
                )
            )
        finally:
            active.speech = None

    @voice_session.on("user_input_transcribed")
    def on_user_input_transcribed(event) -> None:
        text = " ".join(str(getattr(event, "transcript", "")).split())
        if not text:
            return
        if active.speech is not None:
            active.interrupt()
        if bool(getattr(event, "is_final", False)):
            task = asyncio.create_task(process_final_turn(text))
            active.task = task

    @voice_session.on("user_state_changed")
    def on_user_state_changed(event) -> None:
        if str(getattr(event, "new_state", "")) == "speaking" and active.speech is not None:
            active.interrupt()

    try:
        await ctx.connect()
        await voice_session.start(
            agent=SaarthiAgent(state.last_safe_prompt or "What loan amount would you like?"),
            room=ctx.room,
        )
        await asyncio.Event().wait()
    finally:
        active.interrupt()
        await runtime.close()


def run_worker() -> None:
    cli.run_app(server)


if __name__ == "__main__":
    run_worker()
