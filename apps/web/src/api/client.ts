// Minimal typed fetch wrapper for the v1 surface.
// Production swaps the base URL via VITE_API_BASE_URL; in dev Vite
// proxies /v1 to :8000 so we leave the base empty.

import type {
  ApiErrorBody,
  AttemptResponse,
  AuthToken,
  CardsResponse,
  ExportResponse,
  InsightPanel,
  ProfileRequest,
  ProgressResponse,
  StudyPlan,
} from "./types";

const BASE = (import.meta.env?.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const TOKEN_KEY = "edu.token";

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail ?? body.error ?? `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

export function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof localStorage === "undefined") return;
  if (token === null) {
    localStorage.removeItem(TOKEN_KEY);
  } else {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  fetchImpl: typeof fetch = fetch,
): Promise<T> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  const token = getToken();
  if (token) headers.authorization = `Bearer ${token}`;

  const res = await fetchImpl(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let payload: ApiErrorBody = {};
    try {
      payload = (await res.json()) as ApiErrorBody;
    } catch {
      // body wasn't JSON — leave payload empty
    }
    throw new ApiError(res.status, payload);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- Auth -----------------------------------------------------------

export async function signup(
  email: string,
  password: string,
  name?: string,
  fetchImpl?: typeof fetch,
): Promise<AuthToken> {
  return request<AuthToken>(
    "POST",
    "/v1/auth/signup",
    { email, password, name },
    fetchImpl,
  );
}

export async function login(
  email: string,
  password: string,
  fetchImpl?: typeof fetch,
): Promise<AuthToken> {
  return request<AuthToken>(
    "POST",
    "/v1/auth/login",
    { email, password },
    fetchImpl,
  );
}

// ---- Exams ----------------------------------------------------------

export async function getExams(fetchImpl?: typeof fetch) {
  return request<{ exams: { id: string; name: string; slug: string }[] }>(
    "GET",
    "/v1/exams",
    undefined,
    fetchImpl,
  );
}

export async function getInsights(
  examId: string,
  fetchImpl?: typeof fetch,
): Promise<InsightPanel> {
  return request<InsightPanel>(
    "GET",
    `/v1/exams/${encodeURIComponent(examId)}/insights`,
    undefined,
    fetchImpl,
  );
}

// ---- /v1/me ---------------------------------------------------------

export async function setProfile(
  req: ProfileRequest,
  fetchImpl?: typeof fetch,
): Promise<unknown> {
  return request<unknown>("POST", "/v1/me/profile", req, fetchImpl);
}

export async function getPlan(
  days = 7,
  fetchImpl?: typeof fetch,
): Promise<StudyPlan> {
  return request<StudyPlan>(
    "GET",
    `/v1/me/plan?days=${days}`,
    undefined,
    fetchImpl,
  );
}

export async function issueCards(
  topicId: string,
  fetchImpl?: typeof fetch,
): Promise<CardsResponse> {
  return request<CardsResponse>(
    "POST",
    `/v1/me/topics/${encodeURIComponent(topicId)}/cards`,
    {},
    fetchImpl,
  );
}

export async function attemptCard(
  cardId: string,
  answer: string,
  fetchImpl?: typeof fetch,
): Promise<AttemptResponse> {
  return request<AttemptResponse>(
    "POST",
    `/v1/me/cards/${encodeURIComponent(cardId)}/attempt`,
    { answer },
    fetchImpl,
  );
}

export async function getProgress(
  fetchImpl?: typeof fetch,
): Promise<ProgressResponse> {
  return request<ProgressResponse>("GET", "/v1/me/progress", undefined, fetchImpl);
}

export async function exportTopic(
  topicId: string,
  payload: {
    topic_title: string;
    lesson_md: string;
    mindmap_svg: string;
    mindmap_mermaid: string;
  },
  fetchImpl?: typeof fetch,
): Promise<ExportResponse> {
  return request<ExportResponse>(
    "POST",
    `/v1/me/topics/${encodeURIComponent(topicId)}/export`,
    payload,
    fetchImpl,
  );
}
