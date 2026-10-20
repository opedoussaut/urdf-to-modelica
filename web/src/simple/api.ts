/** Client for the conversion API (/api/convert). Jobs are polled with waitJob from ../studio (shared job store). */
export async function convert<T = any>(path: string, method = "GET", data?: unknown): Promise<T> {
  const response = await fetch("/api/convert" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail));
  return body;
}

export type ModeId = "urdfmodelica" | "llm" | "llm_rag";
export const MODE_ORDER: ModeId[] = ["llm", "llm_rag", "urdfmodelica"];

export type Criterion = { id: string; ok: boolean; value?: number | null; detail?: string | null };
export type Score = {
  produced?: boolean;
  loads?: boolean;
  checks?: boolean;
  simulates?: boolean;
  passed: number;
  criteria: Criterion[];
  coverage?: number;
  links_found?: number;
  links_total?: number;
  joints_found?: number;
  joints_total?: number;
  missing_links?: string[];
  missing_joints?: string[];
  load_messages?: string;
  check_messages?: string;
  simulate_messages?: string;
  equations?: number;
  variables?: number;
  kinematics?: { max_position_error_mm: number; mean_position_error_mm: number; worst_link?: [string, number]; max_joint_motion_rad?: number } | null;
};
export type ModeResult = {
  mode: ModeId;
  label: string;
  plain: string;
  verdict: string;
  score: Score;
  main_file?: string;
  model?: string;
  error?: string;
  wall_seconds?: number;
  llm_calls?: number;
  repair_attempts?: number;
  retrieved?: { class: string; query: string }[];
  attempts?: { attempt: number; llm_seconds?: number; code_chars?: number; error?: string }[];
  edits?: { version: number; verdict: string; saved: string; note: string; score: Score }[];
  preprocessing?: string[];
};
export type Report = {
  id: string;
  source: { id: string; label: string; kind: string; links: number; joints: number; movable: number; sha256: string; graph?: boolean; path: string };
  started: string;
  finished?: string;
  ranking?: ModeId[];
  ties?: [ModeId, ModeId][];
  modes: Partial<Record<ModeId, ModeResult>>;
  criteria: Record<string, string>;
};
export type RunSummary = { id: string; source: string; started: string; finished?: string; ranking?: ModeId[]; modes: Record<string, { passed: number; verdict: string }> };
