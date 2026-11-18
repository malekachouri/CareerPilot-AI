import type { components } from "./schema";

type S = components["schemas"];

export type TestSummary = S["TestOut"];
export type Question = S["QuestionOut"];
export type QuestionWithKey = S["QuestionWithKey"];
export type Category = S["CategoryOut"];
export type Company = S["CompanyOut"];
export type CompanyDetail = S["CompanyDetail"];
export type Job = S["JobOut"];
export type GenerateRequest = S["GenerateRequest"];
export type CustomTestIn = S["CustomTestIn"];

// The endpoints below return computed views (no response_model on the API side). Shapes mirror
// apps/api/src/careerpilot/modules/assessments/api.py and service.user_analytics.

export type AttemptQuestion = {
  position: number;
  points: number;
  selected: string[] | null;
  text_answer: string | null;
  flagged: boolean;
  answered: boolean;
  auto_graded: boolean;
  question: Question;
};

export type AttemptState = {
  id: string;
  status: "in_progress" | "submitted";
  mode: string;
  test: { id: string; title: string; time_limit_s: number | null } | null;
  started_at: string;
  deadline_at: string | null;
  server_time: string;
  remaining_seconds: number | null;
  questions: AttemptQuestion[];
};

export type Breakdown = { answered: number; correct: number; accuracy: number };

export type ResultItem = {
  position: number;
  selected: string[] | null;
  text_answer: string | null;
  flagged: boolean;
  is_correct: boolean | null;
  score: number | null;
  points: number;
  graded_by: "key" | "self" | "none" | null;
  time_spent_ms: number;
  question: QuestionWithKey;
};

export type AttemptResults = {
  id: string;
  status: string;
  test: { id: string; title: string } | null;
  started_at: string;
  submitted_at: string | null;
  auto_submitted: boolean;
  score: number | null;
  max_score: number | null;
  percent: number | null;
  correct: number;
  incorrect: number;
  ungraded: number;
  unanswered: number;
  average_time_ms: number | null;
  duration_s: number | null;
  by_category: (Breakdown & { slug: string; name: string })[];
  by_difficulty: (Breakdown & { difficulty: number })[];
  items: ResultItem[];
};

export type Analytics = {
  answered: number;
  correct: number;
  incorrect: number;
  accuracy: number | null;
  average_response_time_ms: number | null;
  attempts: number;
  by_category: (Breakdown & { slug: string; name: string; average_time_ms: number })[];
  by_difficulty: (Breakdown & { difficulty: number })[];
  timeline: { attempt_id: string; submitted_at: string | null; title: string; score_percent: number | null; average_difficulty: number }[];
  repeated_mistakes: { question_id: string; times_wrong: number; stem: string }[];
  knowledge_gaps: (Breakdown & { slug: string; name: string })[];
};

export type GeneratorStatus = { provider: string; model: string; available: boolean; types: string[] };

export const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Beginner",
  2: "Intermediate",
  3: "Advanced",
  4: "Expert",
};

export const TYPE_LABELS: Record<string, string> = {
  mcq_single: "Multiple choice",
  mcq_multi: "Multiple select",
  true_false: "True / False",
  true_false_undetermined: "True / False / Cannot tell",
  scenario: "Scenario",
  situational: "Situational judgment",
  open_ended: "Open-ended",
  coding: "Coding",
  debugging: "Debugging",
  survey: "Questionnaire",
  simulation: "Simulation",
};
