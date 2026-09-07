from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterable
from contextlib import suppress
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    cli,
)
from livekit.plugins import deepgram, rime

from saarthi.config import get_settings
from saarthi.domain.contracts import FinalTranscript, TraceEvent, new_id, utc_now
from saarthi.domain.enums import DeliveryStatus
from saarthi.runtime import build_runtime
from saarthi.services.interpreter import control_command_for_text

logger = logging.getLogger("saarthi.voice")
load_dotenv()
settings = get_settings()
server = AgentServer()
CONTROL_TOPIC = "saarthi-control"
CONTROL_COMMANDS = {
    "stop",
    "pause",
    "resume",
    "repeat",
    "go back",
    "show summary",
    "cancel",
    "submit",
}

OPENING_GREETING_PREFIX = (
    "Welcome to Saarthi, your voice-first loan guidance assistant. "
    "This is a fictional demonstration that creates a reviewable draft only. "
    "It does not approve or submit a loan. I will ask one question at a time, "
    "and you can interrupt me anytime to ask a question, correct an answer, "
    "repeat, pause, or stop. "
)


def build_opening_greeting(opening_prompt: str) -> str:
    """Build a short orientation before the first or resumed field question."""

    return OPENING_GREETING_PREFIX + opening_prompt


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
            build_opening_greeting(self.opening_prompt),
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

    rime_language = "hin" if state.language.lower().startswith("hi") else "eng"
    rime_speaker = (
        settings.rime_hindi_speaker
        if rime_language == "hin"
        else settings.rime_english_speaker
    )

    stt = deepgram.STTv2(
        model=settings.deepgram_model,
        numerals=settings.deepgram_numerals,
        eot_timeout_ms=settings.deepgram_eot_timeout_ms,
        keyterm=[
            "Saarthi",
            "loan amount",
            "loan purpose",
            "tenure",
            "six months",
            "twelve months",
            "eighteen months",
            "twenty-four months",
            "monthly income",
            "existing repayments",
            "interest rate",
            "processing fee",
            "EMI",
            "KYC",
            "salaried",
            "self-employed",
            "one lakh",
            "eighty thousand",
            # Single-word controls are easy to lose in noisy audio. Keep
            # them in the recognizer vocabulary so they reach the
            # deterministic control path instead of the LLM interpreter.
            "stop",
            "pause",
            "resume",
            "repeat",
            "go back",
            "show summary",
            "cancel",
        ],
    )
    tts = rime.TTS(
        model=settings.rime_model,
        speaker=rime_speaker,
        lang=rime_language,
        speed_alpha=settings.rime_speed_alpha,
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
                "min_duration": settings.interruption_min_duration_seconds,
                "min_words": settings.interruption_min_words,
                "false_interruption_timeout": settings.false_interruption_timeout_seconds,
                "resume_false_interruption": True,
                "discard_audio_if_uninterruptible": True,
            },
            preemptive_generation={"enabled": False},
        ),
        min_consecutive_speech_delay=0.0,
    )
    active = ActiveGeneration()

    async def process_final_turn(text: str) -> None:
        turn_received_at = asyncio.get_running_loop().time()
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

        # LiveKit emits the final-transcript callback before it completes its
        # own end-of-turn interruption bookkeeping. Enforce a minimum handoff
        # measured from receipt of the final transcript. Slow model/retrieval
        # work naturally consumes this interval; fast controls and fallbacks
        # wait only for the remaining time.
        elapsed = asyncio.get_running_loop().time() - turn_received_at
        remaining_handoff = max(
            0.0, settings.post_transcript_settle_delay_seconds - elapsed
        )
        if remaining_handoff:
            await asyncio.sleep(remaining_handoff)
        if not active.is_current(local_generation):
            return

        attempt = 0
        while active.is_current(local_generation):
            handle = voice_session.say(response_stream(), allow_interruptions=True)
            active.speech = handle
            try:
                await handle
            finally:
                active.speech = None
            interrupted = bool(getattr(handle, "interrupted", False))
            current = await runtime.repository.get_state(session_id)
            if current is None:
                return
            for segment in current.output_queue:
                if segment.response_id == outcome.response_plan.response_id:
                    segment.delivery_status = (
                        DeliveryStatus.INTERRUPTED
                        if interrupted
                        else DeliveryStatus.DELIVERED
                    )
                    segment.heard_character_count = (
                        0 if interrupted else len(segment.text)
                    )
            if not interrupted:
                current.last_fully_heard_response = [
                    item.model_copy(deep=True)
                    for item in current.output_queue
                    if item.response_id == outcome.response_plan.response_id
                ]
            await runtime.repository.save_state(current)
            await runtime.repository.append_event(
                TraceEvent(
                    event_type="speech_interrupted"
                    if interrupted
                    else "speech_delivered",
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
            if not interrupted:
                return
            if attempt >= settings.interrupted_response_max_retries:
                return

            # A real barge-in produces another finalized turn, whose call to
            # ActiveGeneration.begin invalidates this sequence. If no final
            # turn arrives, treat the interruption as false/untranscribed and
            # replay once so the conversation does not end in silence.
            await asyncio.sleep(settings.interrupted_response_recovery_delay_seconds)
            refreshed = await runtime.repository.get_state(session_id)
            if (
                not active.is_current(local_generation)
                or refreshed is None
                or refreshed.generation_id != outcome.state.generation_id
            ):
                return
            attempt += 1
            await runtime.repository.append_event(
                TraceEvent(
                    event_type="speech_recovery_started",
                    session_id=refreshed.session_id,
                    application_id=refreshed.application_id,
                    trace_id=refreshed.trace_id,
                    component="livekit_voice_worker",
                    outcome="retrying",
                    turn_id=refreshed.current_turn_id,
                    generation_id=refreshed.generation_id,
                    application_revision=refreshed.linked_application_revision,
                    state_version=refreshed.state_version,
                    payload={
                        "response_id": outcome.response_plan.response_id,
                        "attempt": attempt,
                    },
                )
            )

    async def shutdown_after_submission() -> None:
        """End the voice agent after the borrower submits the demo draft."""

        active.interrupt()
        voice_session.shutdown(drain=False)
        ctx.shutdown("borrower submitted the draft")

    def queue_control(command: str) -> None:
        """Run browser controls through the same guarded path as voice controls."""

        if command not in CONTROL_COMMANDS:
            logger.warning("ignoring unsupported control command: %s", command)
            return
        if command == "submit":
            asyncio.create_task(shutdown_after_submission())
            return
        active.interrupt()
        task = asyncio.create_task(process_final_turn(command))
        active.task = task

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket) -> None:
        if packet.topic != CONTROL_TOPIC:
            return
        try:
            payload = json.loads(packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            logger.warning("ignoring malformed control packet")
            return
        if payload.get("type") != "control" or payload.get("session_id") != session_id:
            return
        command = str(payload.get("command", "")).strip().replace("_", " ")
        queue_control(command)

    @voice_session.on("user_input_transcribed")
    def on_user_input_transcribed(event) -> None:
        text = " ".join(str(getattr(event, "transcript", "")).split())
        if not text:
            return
        is_final = bool(getattr(event, "is_final", False))
        command = control_command_for_text(text)

        # Do not force-cancel playback for every interim ASR fragment. VAD
        # and LiveKit already handle ordinary barge-in, and cancelling here
        # makes a false/interim transcript permanently cut off the response.
        # STOP is the one command that must stop local playback immediately.
        if not is_final:
            if command is not None and command.value == "stop":
                active.interrupt()
            return

        # At final-turn time, invalidate the previous generation before the
        # new turn enters the guarded orchestrator.
        if active.speech is not None:
            active.interrupt()
        task = asyncio.create_task(process_final_turn(text))
        active.task = task

    try:
        await ctx.connect()
        await voice_session.start(
            agent=SaarthiAgent(
                state.last_safe_prompt or "What loan amount would you like?"
            ),
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
