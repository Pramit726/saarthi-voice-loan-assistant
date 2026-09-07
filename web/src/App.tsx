import { useEffect, useMemo, useRef, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import {
  createSession,
  getAggregateEvidence,
  getAcceptance,
  getDraft,
  getEvents,
  getSessions,
  getToken,
  recordStopLatency,
  sendControl,
  type AggregateEvidence,
  type Session,
  type SessionSummary,
} from "./api";

type EvidenceEvent = {
  event_id: string;
  event_type: string;
  component: string;
  outcome: string;
  occurred_at: string;
  turn_id?: string | null;
  generation_id?: number;
  application_revision?: number;
  latency_ms?: number | null;
  payload?: Record<string, any>;
};

const FIELD_LABELS: Record<string, string> = {
  requested_amount: "Requested amount",
  loan_purpose: "Loan purpose",
  preferred_tenure: "Preferred tenure",
  employment_type: "Employment type",
  monthly_income: "Monthly income",
  existing_repayments: "Existing repayments",
  city: "City",
  contact_preference: "Contact preference",
};

type VoiceState = "idle" | "connecting" | "listening" | "speaking" | "paused";
type VoiceLanguage = "en-IN" | "hi-IN";
type TranscriptSpeaker = "You" | "Saarthi";
type TranscriptLine = { id: string; speaker: TranscriptSpeaker; text: string };

const LANGUAGE_OPTIONS: Array<{ code: VoiceLanguage; label: string; sublabel: string; voice: string }> = [
  { code: "en-IN", label: "English", sublabel: "Indian English", voice: "Coda · Nadi" },
  { code: "hi-IN", label: "हिन्दी", sublabel: "Hindi voice", voice: "Coda · Nadi" },
];

const VOICE_STATE_COPY: Record<VoiceState, { label: string; title: string; detail: string }> = {
  idle: {
    label: "Standby",
    title: "Ready when you are",
    detail: "Start a private voice draft and Saarthi will guide one question at a time.",
  },
  connecting: {
    label: "Connecting",
    title: "Setting up your session",
    detail: "Creating a private room for this draft.",
  },
  listening: {
    label: "Listening",
    title: "I’m listening",
    detail: "Speak naturally. You can ask a question or correct an earlier answer.",
  },
  speaking: {
    label: "Speaking",
    title: "Saarthi is speaking",
    detail: "You can interrupt or use a control whenever you need to.",
  },
  paused: {
    label: "Paused",
    title: "Your draft is paused",
    detail: "Resume when you are ready. Your confirmed answers remain safe.",
  },
};

function VoiceMark({ state }: { state: VoiceState }) {
  if (state === "speaking") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true" className="voice-mark voice-mark-speaking">
        <path d="M14 31h6M24 23v18M34 16v32M44 23v18M54 29v6" />
      </svg>
    );
  }
  if (state === "listening") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true" className="voice-mark voice-mark-listening">
        <rect x="24" y="10" width="16" height="31" rx="8" />
        <path d="M17 30a15 15 0 0 0 30 0M32 45v9M23 54h18" />
      </svg>
    );
  }
  if (state === "paused") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true" className="voice-mark voice-mark-paused">
        <path d="M24 18v28M40 18v28" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true" className="voice-mark voice-mark-idle">
      <path d="M32 8l3.5 16.5L52 28l-16.5 3.5L32 48l-3.5-16.5L12 28l16.5-3.5L32 8Z" />
      <path d="M50 43l1.7 7.3L59 52l-7.3 1.7L50 61l-1.7-7.3L41 52l7.3-1.7L50 43Z" />
    </svg>
  );
}

function BorrowerView() {
  const [session, setSession] = useState<Session | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [status, setStatus] = useState("Ready to begin");
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [language, setLanguage] = useState<VoiceLanguage>("en-IN");
  const [transcript, setTranscript] = useState<TranscriptLine[]>([]);
  const [liveTranscript, setLiveTranscript] = useState<TranscriptLine | null>(null);
  const [draft, setDraft] = useState<any>(null);
  const [submitted, setSubmitted] = useState(false);
  const [helpRequested, setHelpRequested] = useState(false);
  const audioElements = useRef<Set<HTMLMediaElement>>(new Set());

  useEffect(() => {
    if (!session) return;
    const timer = window.setInterval(() => getDraft(session.session_id).then(setDraft).catch(() => undefined), 1200);
    return () => window.clearInterval(timer);
  }, [session]);

  const start = async () => {
    setVoiceState("connecting");
    setStatus("Creating a private demonstration session...");
    const created = await createSession(language);
    const credentials = await getToken(created.session_id);
    const nextRoom = new Room({ adaptiveStream: true, dynacast: true });
    nextRoom.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
      const speaker: TranscriptSpeaker = participant?.isLocal ? "You" : "Saarthi";
      const interimText = segments.filter((segment) => !segment.final).map((segment) => segment.text).join(" ").trim();
      const finalText = segments.filter((segment) => segment.final).map((segment) => segment.text).join(" ").trim();
      if (interimText) setLiveTranscript({ id: `live-${Date.now()}`, speaker, text: interimText });
      if (finalText) {
        setTranscript((items) => [...items.slice(-7), { id: `${speaker}-${Date.now()}`, speaker, text: finalText }]);
        setLiveTranscript(null);
      }
    });
    nextRoom.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
      const assistantIsSpeaking = speakers.some((participant) => participant.identity !== nextRoom.localParticipant.identity);
      if (assistantIsSpeaking) {
        audioElements.current.forEach((element) => {
          if (element.paused) void element.play().catch(() => undefined);
        });
        setVoiceState("speaking");
        setStatus("Saarthi is speaking");
      } else {
        setVoiceState("listening");
        setStatus("Listening - speak naturally or use a control");
      }
    });
    nextRoom.on(RoomEvent.Disconnected, () => {
      audioElements.current.forEach((element) => {
        element.pause();
        element.remove();
      });
      audioElements.current.clear();
      setRoom((current) => current === nextRoom ? null : current);
      setVoiceState("idle");
      setStatus((current) => current.startsWith("Application marked submitted") ? current : "Voice session ended");
    });
    nextRoom.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === "audio") {
        const element = track.attach();
        element.autoplay = true;
        element.setAttribute("playsinline", "true");
        element.volume = 1;
        document.body.appendChild(element);
        audioElements.current.add(element);
        void element.play().catch(() => undefined);
      }
    });
    await nextRoom.connect(credentials.url, credentials.token);
    await nextRoom.localParticipant.setMicrophoneEnabled(true);
    setSession(created);
    setRoom(nextRoom);
    setVoiceState("listening");
    setStatus("Listening - speak naturally or use a control");
  };

  const control = async (command: string) => {
    if (!session) return;
    const stopStartedAt = command === "stop" ? performance.now() : null;
    let recordedStopLatency: number | null = null;
    let stopRecordingError = false;
    if (command === "stop") {
      // Pause the live audio element, but keep it attached. Detaching it here
      // prevents later assistant turns from becoming audible because
      // TrackSubscribed is not emitted again for the same publication.
      audioElements.current.forEach((element) => element.pause());
      setVoiceState("listening");
      if (stopStartedAt !== null) {
        const stopLatencyMs = Math.max(0, Math.round(performance.now() - stopStartedAt));
        try {
          await recordStopLatency(session.session_id, stopLatencyMs);
          recordedStopLatency = stopLatencyMs;
        } catch (error) {
          console.error("Could not record user-facing stop latency", error);
          stopRecordingError = true;
        }
      }
    }
    if (command === "pause") setVoiceState("paused");
    if (command === "resume") setVoiceState("listening");
    if (room) {
      const packet = JSON.stringify({ type: "control", session_id: session.session_id, command });
      await room.localParticipant.publishData(new TextEncoder().encode(packet), {
        reliable: true,
        topic: "saarthi-control",
      });
    } else {
      await sendControl(session.session_id, command);
    }
    setStatus(command === "cancel" ? "Draft cancelled - nothing submitted" : recordedStopLatency !== null ? `Playback stopped · ${recordedStopLatency} ms recorded` : stopRecordingError ? "Playback stopped, but stop-latency recording failed" : `${command.replace("_", " ")} requested`);
  };

  const fields = draft?.fields ?? {};
  const answeredFields = Object.keys(fields).length;
  const draftComplete = answeredFields === Object.keys(FIELD_LABELS).length;
  const copy = VOICE_STATE_COPY[voiceState];
  const raiseHelpRequest = () => {
    setHelpRequested(true);
    setStatus("Human-help request recorded for this demo");
  };
  const submitApplication = async () => {
    if (!draftComplete || submitted) return;
    setSubmitted(true);
    if (room) {
      const packet = JSON.stringify({ type: "control", session_id: session?.session_id, command: "submit" });
      await room.localParticipant.publishData(new TextEncoder().encode(packet), {
        reliable: true,
        topic: "saarthi-control",
      });
      room.disconnect();
      setRoom(null);
    }
    setVoiceState("idle");
    setStatus("Application marked submitted for this demo; voice agent stopped");
  };
  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Saarthi home"><img className="brand-logo" src="/saarthi-mark.jpg" alt="" /><span className="brand-copy"><strong>Saarthi</strong><small>Voice-first loan guidance</small></span></a>
        <div className="topbar-meta"><span className="provider-pill"><i /> Rime voice · guarded AI</span><span className="draft-badge"><b>{submitted ? "Demo submitted" : "Draft only"}</b><small>{submitted ? "No lender request sent" : "Never submitted by AI"}</small></span></div>
      </header>

      <section className="hero">
        <div><span className="eyebrow">PRIVATE APPLICATION COMPANION</span><h1>A calmer way to<br /><em>get loan-ready.</em></h1><p>Ask questions, make corrections, and review every answer before you decide.</p></div>
        <div className="hero-note"><span className="hero-note-icon"><img src="/saarthi-mark.jpg" alt="" /></span><div><strong>You are in control</strong><small>Saarthi can explain and prepare a draft. Only you can submit it.</small></div></div>
      </section>

      {!session && <section className="language-card" aria-label="Choose voice language">
        <div><span className="eyebrow">VOICE LANGUAGE</span><strong>How would you like to hear Saarthi?</strong><small>Your choice selects the Rime Coda language and voice for this session.</small></div>
        <div className="language-options" role="radiogroup" aria-label="Voice language options">
          {LANGUAGE_OPTIONS.map((option) => <button key={option.code} type="button" role="radio" aria-checked={language === option.code} className={`language-option ${language === option.code ? "selected" : ""}`} onClick={() => setLanguage(option.code)}>
            <span className="language-radio" />
            <span><b>{option.label}</b><small>{option.sublabel}</small></span>
            <em>{option.voice}</em>
          </button>)}
        </div>
      </section>}

      <section className="notice">This prototype uses fictional product terms and non-sensitive answers. Never speak PAN, Aadhaar, OTP, bank details, a phone number, or an email address.</section>

      <div className="grid">
        <section className="card voice-card">
          <div className="voice-stage">
            <div className="voice-stage-top"><span className={`state-pill state-${voiceState}`}><i /> {copy.label}</span><span className="stage-caption">{room ? `${language === "hi-IN" ? "हिन्दी" : "English"} · Rime Coda` : "Voice guide"}</span></div>
            <div className={`orb orb-${voiceState}`} data-active={Boolean(room)} data-state={voiceState}><div className="orb-halo orb-halo-one" /><div className="orb-halo orb-halo-two" /><div className="orb-core"><VoiceMark state={voiceState} /></div></div>
            <h2>{copy.title}</h2>
            <p className="voice-detail">{voiceState === "idle" ? copy.detail : status}</p>
            <p className="voice-support">{copy.detail}</p>
          </div>
          {!session ? <button className="primary" onClick={start}>Start voice draft</button> : submitted ? (
            <div className="session-ended" role="status">Voice agent stopped after your submission.</div>
          ) : (
            <div className="control-dock" aria-label="Voice controls">
              <button onClick={() => control("pause")} className="dock-button"><span>Ⅱ</span> Pause</button>
              <button onClick={() => control("repeat")} className="dock-button"><span>↻</span> Repeat</button>
              <button onClick={() => control("go_back")} className="dock-button"><span>←</span> Go back</button>
              <button onClick={() => control("stop")} className="dock-button dock-stop"><span>■</span> Stop</button>
              <button onClick={() => control("cancel")} className="dock-button dock-cancel"><span>×</span> Cancel</button>
            </div>
          )}
          <div className="transcript" aria-live="polite">
            <div className="transcript-heading"><span>LIVE TRANSCRIPT</span><small>{transcript.length || liveTranscript ? "Speaker-labelled conversation" : "Waiting for speech"}</small></div>
            <div className="transcript-feed">
              {transcript.length || liveTranscript ? <>
                {transcript.map((line) => <div className={`transcript-line transcript-${line.speaker === "You" ? "user" : "assistant"}`} key={line.id}><span>{line.speaker}</span><p>{line.text}</p></div>)}
                {liveTranscript && <div className={`transcript-line transcript-live transcript-${liveTranscript.speaker === "You" ? "user" : "assistant"}`}><span>{liveTranscript.speaker} · live</span><p>{liveTranscript.text}</p></div>}
              </> : <p className="transcript-empty">Your live conversation will appear here.</p>}
            </div>
          </div>
          {session && <div className={`support-panel ${helpRequested ? "is-requested" : ""}`}>
            <div><strong>{helpRequested ? "Human-help request recorded" : "Need more help?"}</strong><span>{helpRequested ? "Demo ticket SUP-DEMO-001 · no personal information was submitted." : "If an answer is unclear or unsatisfactory, you can ask for human review."}</span></div>
            <button className="support-button" onClick={raiseHelpRequest} disabled={helpRequested}>{helpRequested ? "Ticket raised ✓" : "Raise a ticket"}</button>
          </div>}
        </section>

        <section className="card">
          <div className="section-title"><div><span className="eyebrow">YOUR INFORMATION</span><h2>Application draft</h2></div><span className="revision-chip">Revision {draft?.revision ?? 0}</span></div>
          <div className="draft-progress"><span><b>{answeredFields}</b> of {Object.keys(FIELD_LABELS).length} answered</span><div><i style={{ width: `${(answeredFields / Object.keys(FIELD_LABELS).length) * 100}%` }} /></div></div>
          <div className="fields">
            {Object.entries(FIELD_LABELS).map(([key, label]) => (
              <div className="field" key={key}><span>{label}</span><strong>{fields[key]?.typed_value?.toString() ?? "Not answered"}</strong></div>
            ))}
          </div>
          <div className={`submit-panel ${draftComplete ? "is-ready" : ""} ${submitted ? "is-submitted" : ""}`}>
            <div><strong>{submitted ? "Application marked submitted" : draftComplete ? "Ready for your review" : "Complete the draft to continue"}</strong><span>{submitted ? "This is a demo status only. No external lender request was made." : draftComplete ? "Check your answers, then submit when you are ready." : `${Object.keys(FIELD_LABELS).length - answeredFields} answers still needed before the button is enabled.`}</span></div>
            <button className="submit-button" disabled={!draftComplete || submitted} onClick={submitApplication}>{submitted ? "Submitted ✓" : "Submit application"}</button>
          </div>
          {session && <a className="dashboard-link" href={`/?view=dashboard&session=${session.session_id}`}>Open evidence dashboard →</a>}
        </section>
      </div>
    </main>
  );
}

const PIPELINE_EVIDENCE = [
  ["Turn received", "final_transcript_accepted"],
  ["Turn interpreted", "turn_interpreted"],
  ["Draft decision", "application_patch_decided"],
  ["Response released", "response_released"],
] as const;

function EvidenceBarChart({
  title,
  description,
  data,
  tone = "blue",
}: {
  title: string;
  description: string;
  data: Array<{ label: string; value: number; detail?: string }>;
  tone?: "blue" | "teal" | "orange";
}) {
  const max = Math.max(1, ...data.map((item) => item.value));
  const rowHeight = 42;
  const labelWidth = 168;
  const plotWidth = 430;
  const height = Math.max(100, data.length * rowHeight + 28);
  return (
    <section className="chart-panel">
      <div className="chart-heading"><h2>{title}</h2><span>{description}</span></div>
      <svg className="evidence-chart" viewBox={`0 0 640 ${height}`} role="img" aria-label={`${title}: ${data.map((item) => `${item.label} ${item.value}`).join(", ")}`}>
        <line x1={labelWidth} y1="8" x2={labelWidth} y2={height - 12} className="chart-axis" />
        {data.map((item, index) => {
          const y = 16 + index * rowHeight;
          const barWidth = (item.value / max) * plotWidth;
          return (
            <g key={`${item.label}-${index}`}>
              <text x="0" y={y + 14} className="chart-label">{item.label}</text>
              <rect x={labelWidth + 12} y={y} width={plotWidth} height="20" rx="8" className="chart-track" />
              <rect x={labelWidth + 12} y={y} width={Math.max(item.value ? 6 : 0, barWidth)} height="20" rx="8" className={`chart-bar ${tone}`} />
              <text x={labelWidth + 22 + barWidth} y={y + 14} className="chart-value">{item.value}</text>
              {item.detail && <text x={labelWidth + 12} y={y + 34} className="chart-detail">{item.detail}</text>}
              <title>{`${item.label}: ${item.value}${item.detail ? `, ${item.detail}` : ""}`}</title>
            </g>
          );
        })}
      </svg>
    </section>
  );
}

function LatencyChart({ events }: { events: EvidenceEvent[] }) {
  const samples = events
    .filter((event) => typeof event.latency_ms === "number" && ["turn_interpreted", "interpreter_failed", "response_released"].includes(event.event_type))
    .slice(-10)
    .map((event) => ({
      label: `${event.turn_id?.slice(-5) ?? "turn"} · ${event.event_type === "response_released" ? "total" : "interpret"}`,
      value: Math.round(event.latency_ms ?? 0),
    }));
  if (!samples.length) {
    return <section className="chart-panel empty-chart"><div className="chart-heading"><h2>Backend decision latency</h2><span>No latency samples yet</span></div><p>Latency evidence appears after the assistant processes a turn.</p></section>;
  }
  return <EvidenceBarChart title="Interpreter and decision latency" description="milliseconds · latest samples" data={samples.map((sample) => ({ ...sample, detail: `${sample.value} ms` }))} tone="orange" />;
}

const EVENT_TITLES: Record<string, string> = {
  session_created: "Session created",
  final_transcript_accepted: "User turn accepted",
  turn_interpreted: "Turn interpreted",
  grounding_decided: "Grounded answer decided",
  application_patch_decided: "Draft write decided",
  response_released: "Response released",
  response_blocked: "Response blocked by guard",
  speech_delivered: "Speech delivered",
  speech_interrupted: "Speech interrupted",
  speech_recovery_started: "Speech recovery started",
  user_facing_stop_latency_recorded: "User-facing stop latency recorded",
};

function eventTitle(event: EvidenceEvent) {
  return EVENT_TITLES[event.event_type] ?? event.event_type.replaceAll("_", " ");
}

function eventDetail(event: EvidenceEvent) {
  const payload = event.payload ?? {};
  if (event.event_type === "turn_interpreted") {
    return `Route: ${String(payload.route ?? event.outcome).replaceAll("_", " ")}${payload.target_field ? ` · target: ${String(payload.target_field).replaceAll("_", " ")}` : ""}`;
  }
  if (event.event_type === "application_patch_decided") {
    return payload.accepted ? `Draft revision advanced to ${payload.new_revision ?? "the next revision"}.` : `Draft write was not applied: ${String(event.outcome).replaceAll("_", " ")}.`;
  }
  if (event.event_type === "grounding_decided") {
    const factCount = Array.isArray(payload.fact_ids) ? payload.fact_ids.length : 0;
    return `${factCount} approved product fact${factCount === 1 ? "" : "s"} linked to the answer.`;
  }
  if (event.event_type === "response_released") {
    const segmentCount = Array.isArray(payload.segment_ids) ? payload.segment_ids.length : 0;
    return `${segmentCount} spoken segment${segmentCount === 1 ? "" : "s"} released after guard evaluation.`;
  }
  if (event.event_type === "response_blocked") return "The response guard stopped this output from being spoken.";
  if (event.event_type === "speech_interrupted") return "Playback stopped after detected user speech. A finalized new turn cancels it; otherwise recovery may retry once.";
  if (event.event_type === "speech_recovery_started") return "No finalized user turn followed the interruption, so the current safe response is being replayed once.";
  if (event.event_type === "user_facing_stop_latency_recorded") return `Browser click-to-audio-detach latency: ${Math.round(event.latency_ms ?? 0)} ms.`;
  if (event.event_type === "speech_delivered") return "The generated response completed playback.";
  if (event.event_type === "final_transcript_accepted") return "A final speech-recognition result entered the guarded backend.";
  if (event.event_type === "session_created") return "A new draft-only application and conversation state were created.";
  return `Observed outcome: ${event.outcome.replaceAll("_", " ")}.`;
}

function eventTone(event: EvidenceEvent) {
  if (/blocked|failed|rejected|stale/.test(event.outcome) || event.event_type === "response_blocked") return "failure";
  if (event.event_type === "speech_interrupted" || /interrupt|recovery/.test(event.event_type)) return "warning";
  if (event.event_type === "grounding_decided" || event.event_type === "application_patch_decided") return "decision";
  return "normal";
}

function AcceptanceEvidenceTable({
  stopLatencyP95,
  sampleCount,
}: {
  stopLatencyP95: number | null;
  sampleCount: number;
}) {
  const measured = stopLatencyP95 !== null;
  const passed = measured && stopLatencyP95 <= 500;
  return (
    <section className="card acceptance-table-card">
      <div className="table-wrap">
        <table className="acceptance-table">
          <thead><tr><th>Metric</th><th>Observed</th><th>Result</th></tr></thead>
          <tbody>
            <tr>
              <td>User-facing stop latency</td>
              <td>{measured ? `${stopLatencyP95} ms · ${sampleCount} sample${sampleCount === 1 ? "" : "s"}` : "Not recorded"}</td>
              <td><span className={`evidence-status ${!measured ? "pending" : passed ? "pass" : "fail"}`}>{!measured ? "Inconclusive" : passed ? "Pass" : "Miss"}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Dashboard({ initialSessionId }: { initialSessionId: string | null }) {
  const [sessionId, setSessionId] = useState(initialSessionId ?? "");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [aggregate, setAggregate] = useState<AggregateEvidence | null>(null);
  const [events, setEvents] = useState<EvidenceEvent[]>([]);
  const [draft, setDraft] = useState<any>(null);
  const [acceptance, setAcceptance] = useState<any>(null);

  useEffect(() => {
    const loadOverview = () => Promise.all([getSessions(), getAggregateEvidence()]).then(([available, totals]) => {
      setSessions(available);
      setAggregate(totals);
      setSessionId((current) => {
        if (current && available.some((item) => item.session_id === current)) return current;
        const next = available[0]?.session_id ?? "";
        if (next) {
          const url = new URL(window.location.href);
          url.searchParams.set("session", next);
          window.history.replaceState({}, "", url);
        }
        return next;
      });
    });
    loadOverview().catch(() => undefined);
    const timer = window.setInterval(() => loadOverview().catch(() => undefined), 5000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const load = () => Promise.all([getEvents(sessionId), getDraft(sessionId), getAcceptance(sessionId)]).then(([e, d, a]) => { setEvents(e); setDraft(d); setAcceptance(a); });
    load().catch(() => undefined);
    const timer = window.setInterval(() => load().catch(() => undefined), 1500);
    return () => window.clearInterval(timer);
  }, [sessionId]);

  const chooseSession = (nextSessionId: string) => {
    setSessionId(nextSessionId);
    setEvents([]);
    setDraft(null);
    setAcceptance(null);
    const url = new URL(window.location.href);
    url.searchParams.set("session", nextSessionId);
    window.history.replaceState({}, "", url);
  };
  const grounded = events.filter((event) => event.event_type === "grounding_decided");
  const controls = events.filter((event) => /speech|stale|control|stop_latency/.test(event.event_type));
  const answeredFields = Object.keys(draft?.fields ?? {}).length;
  const fieldTotal = 8;
  const pipelineData = PIPELINE_EVIDENCE.map(([label, eventType]) => ({
    label,
    value: events.filter((event) => event.event_type === eventType).length,
  }));
  const safetyData = [
    { label: "Grounded answers", value: grounded.length },
    { label: "Interruptions", value: events.filter((event) => event.event_type === "speech_interrupted").length },
    { label: "Automatic recoveries", value: events.filter((event) => event.event_type === "speech_recovery_started").length },
    { label: "Stop measurements", value: events.filter((event) => event.event_type === "user_facing_stop_latency_recorded").length },
    { label: "Blocked responses", value: events.filter((event) => event.event_type === "response_blocked").length },
    { label: "Stale work blocked", value: events.filter((event) => /stale/.test(event.event_type)).length },
  ];
  const outcomeData = [
    { label: "Released", value: events.filter((event) => event.outcome === "released").length },
    { label: "Accepted", value: events.filter((event) => event.outcome === "accepted").length },
    { label: "Interrupted", value: events.filter((event) => event.outcome === "interrupted").length },
    { label: "Blocked or failed", value: events.filter((event) => /blocked|failed|rejected|stale/.test(event.outcome)).length },
  ];
  const hardFailures = acceptance?.hard_gate_failures?.length ?? 0;
  const turns = new Set(events.map((event) => event.turn_id).filter(Boolean)).size;
  const stopLatencySamples = events.filter((event) => event.event_type === "user_facing_stop_latency_recorded" && typeof event.latency_ms === "number").map((event) => event.latency_ms as number).sort((a, b) => a - b);
  const stopLatencyP95 = stopLatencySamples.length ? Math.round(stopLatencySamples[Math.max(0, Math.ceil(stopLatencySamples.length * 0.95) - 1)]) : null;
  return <main className="shell dashboard">
     <header className="hero dashboard-hero"><div><div className="dashboard-brand"><img className="dashboard-logo" src="/saarthi-mark.jpg" alt="" /><span className="brand-copy"><strong>Saarthi</strong><small>Voice-first loan guidance</small></span></div><span className="eyebrow">OBSERVABILITY AND ACCEPTANCE</span><h1>Saarthi evidence dashboard</h1><p>Current-session evidence with selectable history and aggregate performance.</p></div><div className={`verdict ${acceptance?.verdict ?? "pending"}`}>{acceptance?.verdict ?? "pending"}</div></header>
    <section className="session-toolbar" aria-label="Evidence session selection">
      <div><span className="toolbar-label">Viewing session</span><strong>{sessionId ? sessionId.slice(-12) : "No sessions yet"}</strong></div>
      <label className="session-picker">Choose a session
        <select value={sessionId} onChange={(event) => chooseSession(event.target.value)} disabled={!sessions.length}>
          {!sessions.length && <option value="">No sessions available</option>}
          {sessions.map((item, index) => <option key={item.session_id} value={item.session_id}>
            {index === 0 ? "Latest · " : ""}{item.session_id.slice(-8)} · {item.turn_count} turns · {item.verdict}
          </option>)}
        </select>
      </label>
    </section>
    <section className="aggregate-section">
      <div className="aggregate-heading"><div><span className="eyebrow">ALL-SESSION VIEW</span><h2>Aggregate KPIs</h2></div><span>{aggregate?.session_count ?? 0} sessions · {aggregate?.response_latency_sample_count ?? 0} latency samples</span></div>
      <div className="metric-row aggregate-metrics">
        <article><span>Total turns</span><strong>{aggregate?.turn_count ?? 0}</strong></article>
        <article><span>Interpreter success</span><strong>{aggregate?.interpreter_success_rate_pct ?? 0}%</strong></article>
        <article><span>Decision latency p50</span><strong>{Math.round(aggregate?.response_latency_p50_ms ?? 0)}<small> ms</small></strong></article>
        <article><span>Decision latency p95</span><strong>{Math.round(aggregate?.response_latency_p95_ms ?? 0)}<small> ms</small></strong></article>
        <article><span>Stop latency p95</span><strong>{aggregate?.stop_latency_sample_count ? Math.round(aggregate.stop_latency_p95_ms) : "—"}{aggregate?.stop_latency_sample_count ? <small> ms</small> : null}</strong></article>
        <article><span>Latency target met</span><strong>{aggregate?.latency_target_attainment_pct ?? 0}%</strong></article>
        <article className={(aggregate?.hard_failure_count ?? 0) > 0 ? "metric-alert" : ""}><span>Hard failures</span><strong>{aggregate?.hard_failure_count ?? 0}</strong></article>
      </div>
    </section>
    <div className="scope-divider"><span>Selected session</span><strong>{sessionId ? sessionId.slice(-8) : "—"}</strong></div>
    <div className="metric-row"><article><span>Draft revision</span><strong>{draft?.revision ?? 0}</strong></article><article><span>Trace events</span><strong>{events.length}</strong></article><article><span>Grounded answers</span><strong>{grounded.length}</strong></article><article><span>Control evidence</span><strong>{controls.length}</strong></article><article><span>Selected stop p95</span><strong>{stopLatencyP95 ?? "—"}{stopLatencyP95 !== null ? <small> ms</small> : null}</strong></article></div>
    <AcceptanceEvidenceTable stopLatencyP95={stopLatencyP95} sampleCount={stopLatencySamples.length} />
    <section className="card progress-card">
      <div className="section-title"><h2>Draft completion</h2><strong>{answeredFields} of {fieldTotal} fields</strong></div>
      <div className="progress-track" role="progressbar" aria-label="Draft fields completed" aria-valuenow={answeredFields} aria-valuemin={0} aria-valuemax={fieldTotal}><span style={{ width: `${(answeredFields / fieldTotal) * 100}%` }} /></div>
      <p className="chart-caption">This measures committed application state, not spoken words or model guesses.</p>
    </section>
    <div className="chart-grid">
      <EvidenceBarChart title="Evidence pipeline" description="observed events" data={pipelineData} />
      <EvidenceBarChart title="Safety and recovery signals" description="events supporting the claim" data={safetyData} tone="teal" />
      <EvidenceBarChart title="Event outcomes" description="trace outcome counts" data={outcomeData} tone="blue" />
      <LatencyChart events={events} />
    </div>
    <section className="card timeline-card">
      <div className="timeline-heading">
        <div><h2>Conversation and decision timeline</h2><p>Every guarded state transition, from the accepted user turn to spoken output.</p></div>
        <div className="timeline-summary"><span><strong>{events.length}</strong> events</span><span><strong>{turns}</strong> turns</span><span className={hardFailures ? "summary-failure" : ""}><strong>{hardFailures}</strong> hard failures</span></div>
      </div>
      {events.length ? <div className="timeline" aria-label="Conversation and decision events">{events.map((event, index) => <article className={`event event-${eventTone(event)}`} key={event.event_id}>
        <div className="event-marker" aria-hidden="true"><span>{String(index + 1).padStart(2, "0")}</span></div>
        <div className="event-body">
          <div className="event-meta"><time>{new Date(event.occurred_at).toLocaleTimeString()}</time><span>{event.component}</span>{event.turn_id && <span>turn {event.turn_id.slice(-6)}</span>}</div>
          <strong className="event-title">{eventTitle(event)}</strong>
          <p>{eventDetail(event)}</p>
        </div>
        <div className="event-side"><span className={`outcome outcome-${eventTone(event)}`}>{event.outcome.replaceAll("_", " ")}</span><span>rev {event.application_revision ?? 0}</span>{typeof event.latency_ms === "number" && <span>{Math.round(event.latency_ms)} ms</span>}</div>
      </article>)}</div> : <div className="timeline-empty"><strong>No conversation events yet.</strong><span>Start a voice draft to see recognition, decisions, safeguards, and playback appear here.</span></div>}
    </section>
    <a className="dashboard-link" href="/">← Return to borrower experience</a>
  </main>;
}

export function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const sessionId = params.get("session");
  return params.get("view") === "dashboard" ? <Dashboard initialSessionId={sessionId} /> : <BorrowerView />;
}
