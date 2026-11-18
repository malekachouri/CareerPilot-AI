// Shapes of the coach API (apps/api/src/careerpilot/modules/coach/api.py). Message `data` varies by `kind`.

export type Reference = { n?: number; title: string; heading?: string | null; url?: string | null; license?: string | null; attribution?: string | null; kind: string };

export type CoachMessage = {
  id: string;
  role: "coach" | "user";
  kind: "question" | "answer" | "evaluation" | "insight" | "recommendation" | "hint" | "chat" | "report" | "notice";
  content: string;
  status: "pending" | "done" | "failed";
  created_at: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
};

export type CoachSession = {
  id: string;
  kind: "practice" | "interview";
  agent: { slug: string; name: string; disclaimer: string | null };
  persona: string | null;
  title: string;
  status: "active" | "ended";
  learning_mode: boolean;
  state: {
    step: "awaiting_answer" | "evaluated" | "waiting" | "idle";
    pending: boolean;
    current: { type: string; message_id: string; hints: number; topic: string | null; source: string } | null;
    interview: { main_asked: number; total: number; awaiting_answer: boolean } | null;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  report: Record<string, any> | null;
  created_at: string;
  messages: CoachMessage[];
};

export type AgentInfo = { slug: string; name: string; description: string; categories: string[]; criteria: string[]; answer_format: string; disclaimer: string | null };
export type InterviewInfo = { slug: string; name: string; description: string; agent: string };
export type SessionSummary = { id: string; kind: string; agent: string; persona: string | null; title: string; status: string; learning_mode: boolean; created_at: string; updated_at: string; overall_score: number | null };
export type LearningProfile = { target_role: string; seniority: "junior" | "mid" | "senior"; interview_minutes: number; focus_categories: string[]; language: "en" | "fr" };
