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
export const BASE_LABEL: Record<ModeId, string> = { llm: "AI only", llm_rag: "AI + library search", urdfmodelica: "URDFModelica" };

/** Result keys are a method ("urdfmodelica") or a method run with one local model ("llm:qwen2.5-coder:7b"). */
export const baseOf = (key: string) => key.split(":")[0] as ModeId;
export const modelOf = (key: string, r?: { llm_model?: string }) => (key.includes(":") ? key.slice(key.indexOf(":") + 1) : r?.llm_model);
export const keyLabel = (key: string, r?: { llm_model?: string }) => {
  const model = baseOf(key) === "urdfmodelica" ? undefined : modelOf(key, r);
  return BASE_LABEL[baseOf(key)] + (model ? " · " + model : "");
};
export const orderKeys = (keys: string[]) =>
  [...keys].sort((a, b) => MODE_ORDER.indexOf(baseOf(a)) - MODE_ORDER.indexOf(baseOf(b)) || a.localeCompare(b));
export type LocalModel = { name: string; size_gb: number; default: boolean; parameters?: string };

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
  llm_model?: string;
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
  ranking?: string[];
  ties?: [string, string][];
  modes: Record<string, ModeResult>;
  criteria: Record<string, string>;
};
export type RunSummary = { id: string; source: string; started: string; finished?: string; ranking?: string[]; modes: Record<string, { passed: number; verdict: string }> };
