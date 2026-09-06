import { useEffect, useMemo, useState } from "react";
import { Room, RoomEvent } from "livekit-client";
import {
  createSession,
  getAcceptance,
  getDraft,
  getEvents,
  getToken,
  sendControl,
  type Session,
} from "./api";

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

function BorrowerView() {
  const [session, setSession] = useState<Session | null>(null);
  const [room, setRoom] = useState<Room | null>(null);
  const [status, setStatus] = useState("Ready to begin");
  const [transcript, setTranscript] = useState<string[]>([]);
  const [draft, setDraft] = useState<any>(null);

  useEffect(() => {
    if (!session) return;
    const timer = window.setInterval(() => getDraft(session.session_id).then(setDraft).catch(() => undefined), 1200);
    return () => window.clearInterval(timer);
  }, [session]);

  const start = async () => {
    setStatus("Creating a private demonstration session...");
    const created = await createSession();
    const credentials = await getToken(created.session_id);
    const nextRoom = new Room({ adaptiveStream: true, dynacast: true });
    nextRoom.on(RoomEvent.TranscriptionReceived, (segments, participant) => {
      const text = segments.map((segment) => segment.text).join(" ").trim();
      if (text) setTranscript((items) => [...items.slice(-7), `${participant?.identity ?? "Voice"}: ${text}`]);
    });
    nextRoom.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === "audio") document.body.appendChild(track.attach());
    });
    await nextRoom.connect(credentials.url, credentials.token);
    await nextRoom.localParticipant.setMicrophoneEnabled(true);
    setSession(created);
    setRoom(nextRoom);
    setStatus("Listening - speak naturally or use a control");
  };

  const control = async (command: string) => {
    if (!session) return;
    if (command === "stop" || command === "pause" || command === "cancel") {
      room?.remoteParticipants.forEach((participant) =>
        participant.audioTrackPublications.forEach((publication) => publication.audioTrack?.detach().forEach((node) => node.remove())),
      );
    }
    await sendControl(session.session_id, command);
    setStatus(command === "cancel" ? "Draft cancelled - nothing submitted" : `${command.replace("_", " ")} requested`);
  };

  const fields = draft?.fields ?? {};
  return (
    <main className="shell">
      <header className="hero">
        <div><span className="eyebrow">VOICE-FIRST · SYNTHETIC DEMONSTRATION</span><h1>Saarthi</h1><p>A doubt-aware personal-loan draft assistant that keeps you in control.</p></div>
        <div className="draft-badge">Draft only<br /><small>Never submitted</small></div>
      </header>

      <section className="notice">This prototype uses fictional product terms and non-sensitive answers. Never speak PAN, Aadhaar, OTP, bank details, a phone number, or an email address.</section>

      <div className="grid">
        <section className="card voice-card">
          <div className="orb" data-active={Boolean(room)}><span /></div>
          <h2>{status}</h2>
          {!session ? <button className="primary" onClick={start}>Start voice draft</button> : (
            <div className="controls">
              {["pause", "resume", "repeat", "go_back", "show_summary", "stop", "cancel"].map((item) =>
                <button key={item} onClick={() => control(item)} className={item === "cancel" ? "danger" : "secondary"}>{item.replace("_", " ")}</button>
              )}
            </div>
          )}
          <div className="transcript" aria-live="polite">
            {transcript.length ? transcript.map((line, index) => <p key={`${line}-${index}`}>{line}</p>) : <p>Your live transcript will appear here.</p>}
          </div>
        </section>

        <section className="card">
          <div className="section-title"><h2>Application draft</h2><span>revision {draft?.revision ?? 0}</span></div>
          <div className="fields">
            {Object.entries(FIELD_LABELS).map(([key, label]) => (
              <div className="field" key={key}><span>{label}</span><strong>{fields[key]?.typed_value?.toString() ?? "Not answered"}</strong></div>
            ))}
          </div>
          {session && <a className="dashboard-link" href={`/?view=dashboard&session=${session.session_id}`}>Open evidence dashboard →</a>}
        </section>
      </div>
    </main>
  );
}

function Dashboard({ sessionId }: { sessionId: string }) {
  const [events, setEvents] = useState<any[]>([]);
  const [draft, setDraft] = useState<any>(null);
  const [acceptance, setAcceptance] = useState<any>(null);
  useEffect(() => {
    const load = () => Promise.all([getEvents(sessionId), getDraft(sessionId), getAcceptance(sessionId)]).then(([e, d, a]) => { setEvents(e); setDraft(d); setAcceptance(a); });
    load().catch(() => undefined);
    const timer = window.setInterval(() => load().catch(() => undefined), 1500);
    return () => window.clearInterval(timer);
  }, [sessionId]);
  const grounded = events.filter((event) => event.event_type === "grounding_decided");
  const controls = events.filter((event) => /speech|stale|control/.test(event.event_type));
  return <main className="shell dashboard">
    <header className="hero"><div><span className="eyebrow">OBSERVABILITY AND ACCEPTANCE</span><h1>Saarthi evidence dashboard</h1><p>Session {sessionId}</p></div><div className={`verdict ${acceptance?.verdict ?? "pending"}`}>{acceptance?.verdict ?? "pending"}</div></header>
    <div className="metric-row"><article><span>Draft revision</span><strong>{draft?.revision ?? 0}</strong></article><article><span>Trace events</span><strong>{events.length}</strong></article><article><span>Grounded answers</span><strong>{grounded.length}</strong></article><article><span>Control evidence</span><strong>{controls.length}</strong></article></div>
    <section className="card"><h2>Conversation and decision timeline</h2><div className="timeline">{events.map((event) => <div className="event" key={event.event_id}><time>{new Date(event.occurred_at).toLocaleTimeString()}</time><strong>{event.event_type.replaceAll("_", " ")}</strong><span>{event.component} · {event.outcome}</span></div>)}</div></section>
    <a className="dashboard-link" href="/">← Return to borrower experience</a>
  </main>;
}

export function App() {
  const params = useMemo(() => new URLSearchParams(window.location.search), []);
  const sessionId = params.get("session");
  return params.get("view") === "dashboard" && sessionId ? <Dashboard sessionId={sessionId} /> : <BorrowerView />;
}
