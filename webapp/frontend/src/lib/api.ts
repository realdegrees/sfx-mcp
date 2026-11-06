export interface Sound {
  id: number;
  name: string;
  duration: number;
  tags: string[];
  preview_url: string;
  license: string;
  url?: string;
  local_path?: string;
  user_tags?: string[];
}

export interface Render {
  name: string;
  duration: number | null;
  modified: number;
  has_project: boolean;
}

export interface Review {
  status: "picked" | "rejected" | "modify" | null;
  note: string;
}

export interface Candidate extends Render {
  description: string;
  source: string;
  revised: string;
  review: Review;
}

export interface Slot {
  key: string;
  title: string;
  use: string;
  pick: string;
  round?: string;
  candidates: Candidate[];
}

export interface Submission {
  status?: "waiting" | "working" | "done";
  round?: string;
  submitted_at?: string;
  counts?: { picked: number; rejected: number; modify: number; pending: number };
  modify?: { name: string; slot: string; note: string }[];
  agent_message?: string;
}

export interface McpTool {
  name: string;
  description: string;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return (await r.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`${path}: ${r.status} ${text}`);
  }
  return (await r.json()) as T;
}

export const api = {
  health: () => get<{ status: string; server: string; version: string; has_api_key: boolean }>("/api/health"),
  search: (q: string) =>
    get<{ success: boolean; results: Sound[]; total: number; page: number; has_more: boolean }>(
      `/api/sounds/search?q=${encodeURIComponent(q)}`,
    ),
  local: (tag?: string) =>
    get<{ success: boolean; results: Sound[]; total: number }>(
      tag ? `/api/sounds/local?tag=${encodeURIComponent(tag)}` : "/api/sounds/local",
    ),
  download: (sound_id: number) => post<unknown>("/api/sounds/download", { sound_id }),
  renders: () => get<{ success: boolean; results: Render[]; total: number }>("/api/renders"),
  board: () => get<{ success: boolean; id: string; title: string; slots: Slot[] }>("/api/renders/board"),

  picked: () => get<{ success: boolean; slots: Slot[] }>("/api/renders/picked"),
  pickRemaining: (slot?: string) =>
    post<{ success: boolean; picked: string[] }>("/api/renders/pick-remaining", { slot: slot ?? null }),
  submission: () => get<{ success: boolean; submission: Submission }>("/api/renders/submission"),
  submit: () => post<{ success: boolean; submission: Submission }>("/api/renders/submission", {}),
  review: (name: string, review: Review) =>
    post<{ success: boolean; review: Review }>(`/api/renders/${encodeURIComponent(name)}/review`, review),
  tools: () => get<{ tools: McpTool[]; count: number }>("/api/tools"),
  status: () =>
    get<{
      status: string;
      version: string;
    }>("/api/health"),
};
