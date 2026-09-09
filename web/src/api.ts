export type Session = {
  session_id: string;
  application_id: string;
  participant_id: string;
  trace_id: string;
  room_name: string;
  pending_field: string | null;
  opening_prompt: string;
  language?: "en-IN";
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
  stop_latency_sample_count: number;
  stop_latency_average_ms: number;
  stop_latency_p95_ms: number;
  stop_latency_target_attainment_pct: number;
  latency_target_attainment_pct: number;
  pass_rate_pct: number;
  grounded_answer_count: number;
  failed_closed_count: number;
  hard_failure_count: number;
};

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const apiUrl = (path: string) => `${API_BASE_URL}${path}`;

const json = async <T>(response: Response): Promise<T> => {
  if (!response.ok) throw new Error((await response.text()) || response.statusText);
  return response.json() as Promise<T>;
};

export const createSession = () =>
  fetch(apiUrl("/api/sessions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language: "en-IN" }),
  }).then((response) => json<Session>(response));

export const getToken = (sessionId: string) =>
  fetch(apiUrl("/api/livekit/token"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  }).then((response) => json<{ url: string; token: string }>(response));

export const sendControl = (sessionId: string, command: string) =>
  fetch(apiUrl(`/api/sessions/${sessionId}/controls`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  }).then((response) => json<Record<string, unknown>>(response));

export const getDraft = (sessionId: string) =>
  fetch(apiUrl(`/api/sessions/${sessionId}/draft`)).then((response) => json<any>(response));

export const getEvents = (sessionId: string) =>
  fetch(apiUrl(`/api/sessions/${sessionId}/events`)).then((response) => json<any[]>(response));

export const getAcceptance = (sessionId: string) =>
  fetch(apiUrl(`/api/sessions/${sessionId}/acceptance`)).then((response) => json<any>(response));

export const getSessions = () =>
  fetch(apiUrl("/api/sessions?limit=100")).then((response) => json<SessionSummary[]>(response));

export const getAggregateEvidence = () =>
  fetch(apiUrl("/api/evidence/aggregate")).then((response) => json<AggregateEvidence>(response));

export const recordStopLatency = (sessionId: string, latencyMs: number) =>
  fetch(apiUrl(`/api/sessions/${sessionId}/metrics/stop-latency`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ latency_ms: latencyMs }),
  }).then((response) => json<{ recorded: boolean; latency_ms: number }>(response));
