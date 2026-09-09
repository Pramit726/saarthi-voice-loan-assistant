import { afterEach, describe, expect, it, vi } from "vitest";

import { createSession, getAggregateEvidence, getSessions, getToken, sendControl } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("API client", () => {
  it("creates a synthetic draft session", async () => {
    const session = {
      session_id: "session-test",
      application_id: "application-test",
      participant_id: "borrower-test",
      trace_id: "trace-test",
      room_name: "saarthi-session-test",
      pending_field: "requested_amount",
      opening_prompt: "What loan amount would you like?",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(session), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createSession()).resolves.toEqual(session);
    expect(fetchMock).toHaveBeenCalledWith("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ language: "en-IN" }),
    });
  });

  it("requests scoped LiveKit credentials for the created session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ url: "wss://example.test", token: "token" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await getToken("session-test");

    expect(fetchMock).toHaveBeenCalledWith("/api/livekit/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: "session-test" }),
    });
  });

  it("sends explicit user controls to the current session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await sendControl("session-test", "cancel");

    expect(fetchMock).toHaveBeenCalledWith("/api/sessions/session-test/controls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: "cancel" }),
    });
  });

  it("surfaces an API failure instead of treating it as success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("provider unavailable", { status: 502 })),
    );

    await expect(createSession()).rejects.toThrow("provider unavailable");
  });

  it("loads selectable sessions and aggregate evidence", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ session_count: 4 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await getSessions();
    await expect(getAggregateEvidence()).resolves.toMatchObject({ session_count: 4 });

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/sessions?limit=100");
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/evidence/aggregate");
  });
});
