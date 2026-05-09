// Unit tests for the typed API client. We pass an injectable ``fetch``
// so we can assert on requests/responses without spinning up a server.
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  attemptCard,
  exportTopic,
  getInsights,
  getPlan,
  getProgress,
  issueCards,
  login,
  setProfile,
  setToken,
  signup,
} from "../src/api/client";

class MemoryStorage {
  private store: Record<string, string> = {};
  getItem(k: string) { return this.store[k] ?? null; }
  setItem(k: string, v: string) { this.store[k] = v; }
  removeItem(k: string) { delete this.store[k]; }
  clear() { this.store = {}; }
  get length() { return Object.keys(this.store).length; }
  key(i: number) { return Object.keys(this.store)[i] ?? null; }
}

// jsdom isn't loaded; fake just enough of localStorage.
(globalThis as { localStorage?: Storage }).localStorage = new MemoryStorage();

afterEach(() => {
  setToken(null);
  vi.restoreAllMocks();
});

function jsonFetch(status: number, body: unknown): typeof fetch {
  return vi.fn(async () =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  ) as unknown as typeof fetch;
}

describe("auth", () => {
  it("signup posts to /v1/auth/signup and stores nothing yet", async () => {
    const fakeFetch = jsonFetch(201, { token: "tok_a", user_id: "u_1" });
    const res = await signup("a@x.com", "supersecret-pw", "Alice", fakeFetch);
    expect(res.token).toBe("tok_a");
    expect(fakeFetch).toHaveBeenCalledWith(
      "/v1/auth/signup",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("login translates 401 into ApiError", async () => {
    const fakeFetch = jsonFetch(401, { detail: "invalid credentials" });
    await expect(login("a@x.com", "wrong", fakeFetch)).rejects.toBeInstanceOf(ApiError);
  });

  it("setToken adds Authorization header on subsequent calls", async () => {
    setToken("tok_b");
    const fakeFetch = jsonFetch(200, { topics: [] });
    await getProgress(fakeFetch);
    const headers = (fakeFetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][1].headers;
    expect(headers.authorization).toBe("Bearer tok_b");
  });
});

describe("v1/me endpoints", () => {
  it("setProfile sends ISO date and exam id", async () => {
    setToken("tok_z");
    const fakeFetch = jsonFetch(200, {});
    await setProfile(
      {
        exam_id: "aws-ccp",
        exam_date: "2026-08-01T00:00:00Z",
        daily_minutes: 60,
        language: "en",
      },
      fakeFetch,
    );
    const [, init] = (fakeFetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(init.body as string);
    expect(body.exam_id).toBe("aws-ccp");
    expect(body.daily_minutes).toBe(60);
  });

  it("getPlan accepts a days param", async () => {
    setToken("t");
    const fakeFetch = jsonFetch(200, { user_id: "u", exam_id: "x", exam_date: "", days_to_exam: 1, daily_minutes: 60, days: [] });
    await getPlan(3, fakeFetch);
    expect((fakeFetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/v1/me/plan?days=3",
    );
  });

  it("issueCards URL-encodes the topic id", async () => {
    setToken("t");
    const fakeFetch = jsonFetch(200, { cards: [] });
    await issueCards("cloud-concepts.benefits", fakeFetch);
    expect((fakeFetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe(
      "/v1/me/topics/cloud-concepts.benefits/cards",
    );
  });

  it("attemptCard surfaces score and gap", async () => {
    setToken("t");
    const fakeFetch = jsonFetch(200, {
      score: 1.0,
      correct: true,
      gap: "",
      due_at: "2026-05-08T00:00:00Z",
    });
    const res = await attemptCard("c1", "answer", fakeFetch);
    expect(res.correct).toBe(true);
    expect(res.due_at).toBeTruthy();
  });

  it("exportTopic returns a downloadable URL", async () => {
    setToken("t");
    const fakeFetch = jsonFetch(200, {
      artefact_id: "art_1",
      url: "file:///tmp/bundle.zip",
      size_bytes: 4096,
    });
    const res = await exportTopic(
      "x",
      { topic_title: "X", lesson_md: "", mindmap_svg: "<svg/>", mindmap_mermaid: "" },
      fakeFetch,
    );
    expect(res.url.startsWith("file://")).toBe(true);
  });

  it("getInsights round-trips provenance", async () => {
    const fakeFetch = jsonFetch(200, {
      exam_id: "aws-ccp",
      cutoffs: [{ year: 2024, cutoff_score: 700, max_score: 1000, source: "blueprint" }],
      selection_pct: [{ year: 2024, pct: 73, source: "stats", estimated: true }],
      heatmap: [{ topic_id: "x", pyq_count: 1 }],
      sources: ["blueprint", "stats"],
    });
    const panel = await getInsights("aws-ccp", fakeFetch);
    expect(panel.cutoffs[0].source).toBe("blueprint");
    expect(panel.selection_pct[0].estimated).toBe(true);
  });
});

describe("error shape", () => {
  it("ApiError carries status + body", async () => {
    const fakeFetch = jsonFetch(429, { error: "rate_limited", limit: 60 });
    try {
      await getProgress(fakeFetch);
      throw new Error("expected throw");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      const e = err as ApiError;
      expect(e.status).toBe(429);
      expect(e.body.error).toBe("rate_limited");
    }
  });
});
