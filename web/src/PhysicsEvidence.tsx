import { useState } from "react";
import { request } from "./studio";

type Point = {
  time: number; z: number; x: number; fingerZ: number; gripGap: number;
  leftNormal: number; rightNormal: number; tableNormal: number;
};
type Evidence = {
  model: string; role: string; physics_claim: string; frame: string;
  source_csv_sha256: string; modelica_source_sha256: string;
  total_samples: number; metrics: Record<string, number | string>;
  samples: Point[];
};
/** Read-only numerical evidence, deliberately NOT coupled to the live robot/cube scene. */
export default function PhysicsEvidence() {
  const [data, setData] = useState<Evidence | null>(null);
  const [failure, setFailure] = useState("");
  const [loading, setLoading] = useState(false);
  const [sampleIndex, setSampleIndex] = useState(0);
  async function load() {
    setLoading(true); setFailure(""); setData(null);
    try {
      const result = await request("/physics/grasp-surrogate") as Evidence;
      setData(result); setSampleIndex(0);
    } catch (error) {
      setFailure(String(error));
    } finally { setLoading(false); }
  }
  const point = data?.samples[sampleIndex];
  return (
    <details className="wb-card" aria-label="OpenModelica grasp surrogate evidence">
      <summary><strong>Modelica physics evidence</strong> - isolated two-finger surrogate (not live ALOHA physics)</summary>
      <p>This experiment uses OpenModelica-computed motion and contact forces. It does not control the leader, move the live cube, or prove real ALOHA grasp stability.</p>
      <button type="button" disabled={loading} onClick={load}>{loading ? "Reading Modelica result…" : "Load validated OpenModelica grasp result"}</button>
      {failure && <p role="alert">Evidence unavailable: {failure}. Run <code>python -m kkh.engineering.grasp_experiment</code> locally first.</p>}
      {data && point && <div>
        <p><strong>{data.model}</strong> · {data.total_samples} recorded solver rows; showing {data.samples.length} sampled points.</p>
        <p>{data.physics_claim}</p>
        <label>Inspect simulated time: {point.time.toFixed(3)} s
          <input aria-label="Surrogate simulation time" type="range" min="0" max={data.samples.length - 1} value={sampleIndex}
            onChange={e => setSampleIndex(Number(e.target.value))}/>
        </label>
        <p>Cube centre height: {(point.z * 1000).toFixed(1)} mm · Finger height: {(point.fingerZ * 1000).toFixed(1)} mm · Gap: {(point.gripGap * 1000).toFixed(1)} mm</p>
        <p>Left/right normal: {point.leftNormal.toFixed(2)} / {point.rightNormal.toFixed(2)} N · Table normal: {point.tableNormal.toFixed(2)} N</p>
        <p>Max finger penetration: {(Number(data.metrics.max_finger_penetration_m) * 1000).toFixed(2)} mm; max table penetration: {(Number(data.metrics.max_table_penetration_m) * 1000).toFixed(2)} mm.</p>
        <small>Coordinate frame: {data.frame}. CSV SHA-256: {data.source_csv_sha256}. Model SHA-256: {data.modelica_source_sha256}.</small>
      </div>}
    </details>
  );
}
