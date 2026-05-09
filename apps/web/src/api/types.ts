// TypeScript shapes mirroring the FastAPI response models. In a later
// pass these will be auto-generated from the OpenAPI schema; for v0.1
// the server-side Pydantic models change rarely enough that hand-rolled
// types keep the demo simple.

export type Language = "en" | "hi";

export interface AuthToken {
  token: string;
  user_id: string;
}

export interface ProfileRequest {
  exam_id: string;
  exam_date: string; // ISO timestamp
  daily_minutes: number;
  level?: "novice" | "intermediate" | "advanced";
  language?: Language;
}

export interface PlanTopic {
  topic_id: string;
  title: string;
  minutes: number;
  score: number;
}

export interface PlanDay {
  date: string;
  topics: PlanTopic[];
}

export interface StudyPlan {
  user_id: string;
  exam_id: string;
  exam_date: string;
  days_to_exam: number;
  daily_minutes: number;
  days: PlanDay[];
}

export interface Card {
  id: string;
  type: "recall" | "mcq" | "short";
  prompt: string;
  source_pyq_id: string | null;
}

export interface CardsResponse {
  cards: Card[];
}

export interface AttemptResponse {
  score: number;
  correct: boolean;
  gap: string;
  due_at: string | null;
}

export interface ProgressTopic {
  topic_id: string;
  mastery: number;
  last_touched: string;
}

export interface ProgressResponse {
  topics: ProgressTopic[];
}

export interface InsightCutoff {
  year: number;
  cutoff_score: number;
  max_score: number;
  source: string;
}

export interface InsightSelection {
  year: number;
  pct: number;
  source: string;
  estimated?: boolean;
}

export interface InsightHeatmap {
  topic_id: string;
  pyq_count: number;
}

export interface InsightPanel {
  exam_id: string;
  cutoffs: InsightCutoff[];
  selection_pct: InsightSelection[];
  heatmap: InsightHeatmap[];
  sources: string[];
}

export interface ExportResponse {
  artefact_id: string;
  url: string;
  size_bytes: number;
}

export interface ApiErrorBody {
  detail?: string;
  error?: string;
}
