export type Session = {
  session_id: string;
  application_id: string;
  participant_id: string;
  trace_id: string;
  room_name: string;
  pending_field: string | null;
  opening_prompt: string;
};

export type SessionSummary = {
  session_id: string;
  created_at: string;
  updated_at: string;
  status: string;
  pending_field: string | null;
  application_revision: number;
  turn_count: number;
  verdict: string;
};

export type AggregateEvidence = {
  session_count: number;
  evaluated_session_count: number;
  turn_count: number;
  interpreter_success_rate_pct: number;
  response_latency_sample_count: number;
  response_latency_average_ms: number;
  response_latency_p50_ms: number;
  response_latency_p95_ms: number;
  latency_target_attainment_pct: number;
  pass_rate_pct: number;
  grounded_answer_count: number;
  failed_closed_count: number;
  hard_failure_count: number;
};

const json = async <T>(response: Response): Promise<T> => {
  if (!response.ok) throw new Error((await response.text()) || response.statusText);
  return response.json() as Promise<T>;
};

export const createSession = () =>
  fetch("/api/sessions", { method: "POST" }).then((response) => json<Session>(response));

export const getToken = (sessionId: string) =>
  fetch("/api/livekit/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  }).then((response) => json<{ url: string; token: string }>(response));

export const sendControl = (sessionId: string, command: string) =>
  fetch(`/api/sessions/${sessionId}/controls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  }).then((response) => json<Record<string, unknown>>(response));

export const getDraft = (sessionId: string) =>
  fetch(`/api/sessions/${sessionId}/draft`).then((response) => json<any>(response));

export const getEvents = (sessionId: string) =>
  fetch(`/api/sessions/${sessionId}/events`).then((response) => json<any[]>(response));

export const getAcceptance = (sessionId: string) =>
  fetch(`/api/sessions/${sessionId}/acceptance`).then((response) => json<any>(response));

export const getSessions = () =>
  fetch("/api/sessions?limit=100").then((response) => json<SessionSummary[]>(response));

export const getAggregateEvidence = () =>
  fetch("/api/evidence/aggregate").then((response) => json<AggregateEvidence>(response));
