export interface Validation {
  ok: boolean;
  forward_kinematics: {
    max_position_error_m: number;
    links_checked: number;
    samples: number;
  };
  trajectory_max_error: number;
  mimic_max_error: number;
  limit_violations: string[];
}
export interface Run {
  run_id: string;
  success: boolean;
  experiment?: string;
  started: string;
  wall_seconds?: number;
  validation?: Validation;
  simulation?: { data: { timeTotal: number; resultFile: string } };
  results?: {
    samples: number;
    n_moving_joints: number;
    results_file: string;
    ee_path_length_m: Record<string, number>;
  };
  checks?: Record<string, { data: { equations: number; variables: number } }>;
}
export interface Playback {
  time: number[];
  links: Record<string, number[][]>;
  joints: Record<
    string,
    { q: number[]; qd: number[]; effort: number[]; unit: string }
  >;
  end_effectors: Record<string, number[][]>;
}
export interface Joint {
  name: string;
  type: string;
  parent: string;
  child: string;
  axis: number[] | null;
  limit: {
    lower: number | null;
    upper: number | null;
    effort: number;
    velocity: number;
  } | null;
  mimic: [string, number, number] | null;
  actuators: string[] | null;
  function: string | null;
}
export interface Studio {
  manifest: {
    variant: { name: string };
    totals: { links: number; joints: number; driven: number; mimic: number };
    models: Record<string, { joints: Joint[] }>;
    missing_information: string[];
    assumptions: string[];
    discrepancies: Record<string, unknown>[];
  };
  baseline: Run;
  ontology: {
    backend?: string;
    asserted_triples: number;
    closure_triples?: number;
    shacl: { conforms: boolean };
    reasoning: Record<string, { explicit: boolean; inferred: boolean }>;
    graphdb_verified?: boolean;
    graphdb_blocker?: string;
  };
  benchmark: Benchmark | null;
  reference_benchmark?: {
    equations: number;
    joints_outside_limits: number;
    mimic_max_error: number;
    source_preprocessing_matches_current: boolean;
  };
  scenarios: Record<string, { title: string; description: string }>;
}
export interface Benchmark {
  model: string;
  ontology_backend: string;
  max_attempts?: number;
  repeats?: number;
  scope: string;
  interpretation: string;
  summary: Record<
    string,
    {
      trials: number;
      parameter_correct: number;
      executable: number;
      engineering_valid: number;
      first_attempt_valid?: number;
      repair_iterations?: number;
      mean_wall_seconds: number;
    }
  >;
}
export interface Health {
  graphdb: { ok: boolean; note?: string; error?: string };
  ollama: { ok: boolean; models?: string[] };
  openmodelica: { installed: boolean };
}
export interface Evidence {
  id: string;
  joint?: string;
  property?: string;
  value?: string;
  unit?: string;
  description?: string;
  source?: string;
  backend?: string;
}
export interface Answer {
  answer: string;
  citations: string[];
  proposed_change: string;
  evidence: Evidence[];
  model: string;
  audit_id: string;
  metrics: { eval_count: number };
  citation_check: string;
}
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || response.statusText);
  }
  return response.json();
}
