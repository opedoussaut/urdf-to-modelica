export type Doc = {
  id: string;
  kind: string;
  name: string;
  version: number;
  created: string;
  updated: string;
  data: Record<string, any>;
};
export type Context = {
  selected: string;
  robot: string;
  file: string;
  model?: string;
  model_revision?: string;
  trajectory?: string;
  run?: string;
};
export const endpoint = "/api/workbench";
export async function request<T = any>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  const response = await fetch(endpoint + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  return body;
}
export async function waitJob(
  record: Doc,
  progress?: (record: Doc) => void,
): Promise<any> {
  let next = record;
  while (next.data.status === "running") {
    progress?.(next);
    await new Promise((resolve) => setTimeout(resolve, 1200));
    next = await request("/job/" + record.id);
  }
  if (next.data.status !== "complete")
    throw new Error(next.data.error || "Job interrupted");
  return next.data.result;
}
export function message(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
