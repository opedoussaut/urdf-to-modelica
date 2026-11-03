import { useMemo, useState } from "react";
import Markdown from "react-markdown";
import { ArrowLeft, ArrowRight, BookA, ExternalLink, Map as MapIcon, Quote } from "lucide-react";
import ArmView from "./ArmView";
import { PARTS, type Part } from "./robotParts";
import { CONCEPTS, GLOSSARY, REGIONS, ROUTE, conceptById, type Definition, type Visual } from "./atlasContent";
import "./atlas.css";

/** Physical AI Atlas: a browsable map of the concepts behind the studio (no course, no quiz). */
export default function Atlas({ open }: { open: (i: number) => void }) {
  const params = new URLSearchParams(location.search);
  const [id, setId] = useState(() => conceptById(params.get("topic"))?.id || ROUTE[0]);
  const [view, setView] = useState<"map" | "glossary">(() => (params.get("topic") === "glossary" ? "glossary" : "map"));
  const c = conceptById(id)!;
  const i = ROUTE.indexOf(id);
  const setUrl = (topic: string) => {
    try {
      const u = new URL(location.href);
      u.searchParams.set("ws", "atlas");
      u.searchParams.set("topic", topic);
      history.replaceState(null, "", u);
    } catch {}
  };
  const go = (next: string) => {
    setId(next);
    setView("map");
    setUrl(next);
    requestAnimationFrame(() => document.querySelector(".atlas-article")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  };
  const showGlossary = () => {
    setView("glossary");
    setUrl("glossary");
  };
  const region = REGIONS.find((r) => r.id === c.region)!;
  const [lead, ...more] = c.visuals;
  return (
    <div className="lab atlas">
      <header className="atlas-head">
        <div>
          <span className="lab-eyebrow">
            <MapIcon size={13} /> PHYSICAL AI ATLAS
          </span>
          <h1>The ideas behind the studio, one map</h1>
          <p>{CONCEPTS.length} short concepts, from what Physical AI is to why simulations and reality disagree. Each page gives the reference definitions with their sources, pictures, and where to see it in the studio.</p>
        </div>
        <div className="atlas-views" role="tablist" aria-label="Atlas view">
          <button role="tab" aria-selected={view === "map"} className={view === "map" ? "on" : ""} onClick={() => go(id)}>
            <MapIcon size={14} /> Concepts
          </button>
          <button role="tab" aria-selected={view === "glossary"} className={view === "glossary" ? "on" : ""} onClick={showGlossary}>
            <BookA size={14} /> Glossary · {GLOSSARY.length} terms
          </button>
        </div>
      </header>

      <nav className="atlas-map" aria-label="Atlas map">
        {REGIONS.map((r, ri) => (
          <section key={r.id} className={"atlas-region" + (view === "map" && r.id === c.region ? " here" : "")} style={{ ["--rc" as any]: r.color }}>
            <span className="atlas-region-n">{ri + 1}</span>
            <b>{r.label}</b>
            <small>{r.blurb}</small>
            <div className="atlas-chips">
              {CONCEPTS.filter((x) => x.region === r.id).map((x) => (
                <button key={x.id} className={view === "map" && x.id === id ? "on" : ""} aria-current={view === "map" && x.id === id ? "page" : undefined} onClick={() => go(x.id)}>
                  {x.title.replace(/ - .*$/, "")}
                </button>
              ))}
            </div>
          </section>
        ))}
      </nav>

      {view === "glossary" ? (
        <Glossary go={go} />
      ) : (
        <article className="atlas-article" style={{ ["--rc" as any]: region.color }}>
          <div className="atlas-article-main">
            <span className="atlas-tag">
              {region.label} · {i + 1} of {ROUTE.length}
            </span>
            <h2>{c.title}</h2>
            <p className="atlas-gist">{c.gist}</p>
            <Figure v={lead} />
            <Definitions defs={c.definitions} />
            <div className="atlas-body">
              <Markdown>{c.body}</Markdown>
            </div>
            {more.length > 0 && (
              <section className="atlas-more">
                <h3>More pictures</h3>
                {more.map((v) => (
                  <Figure key={v} v={v} />
                ))}
              </section>
            )}
          </div>
          <aside className="atlas-side">
            <div className="atlas-box">
              <h3>See it in the studio</h3>
              {c.studio.map((s) => (
                <button key={s.page + s.label} className="atlas-go" onClick={() => open(s.page)}>
                  <span>
                    <b>{s.label}</b>
                    <small>{s.what}</small>
                  </span>
                  <ExternalLink size={14} />
                </button>
              ))}
            </div>
            <div className="atlas-box">
              <h3>Terms on this page</h3>
              <div className="atlas-related">
                {c.definitions.map((d) => (
                  <button key={d.term} onClick={() => document.getElementById("def-" + slug(d.term))?.scrollIntoView({ behavior: "smooth", block: "center" })}>
                    {d.term}
                  </button>
                ))}
              </div>
            </div>
            <div className="atlas-box">
              <h3>Related</h3>
              <div className="atlas-related">
                {c.related.map((r) => {
                  const rc = conceptById(r)!;
                  return (
                    <button key={r} onClick={() => go(r)}>
                      {rc.title}
                    </button>
                  );
                })}
              </div>
            </div>
          </aside>
          <footer className="atlas-pager">
            <button disabled={i === 0} onClick={() => go(ROUTE[i - 1])}>
              <ArrowLeft size={15} />
              <span>
                <small>Previous</small>
                {i > 0 ? conceptById(ROUTE[i - 1])!.title : "-"}
              </span>
            </button>
            <button disabled={i === ROUTE.length - 1} onClick={() => go(ROUTE[i + 1])} className="next">
              <span>
                <small>Next</small>
                {i < ROUTE.length - 1 ? conceptById(ROUTE[i + 1])!.title : "-"}
              </span>
              <ArrowRight size={15} />
            </button>
          </footer>
        </article>
      )}
    </div>
  );
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-");

/* ---------- definitions ---------- */

function DefText({ d }: { d: Definition }) {
  return d.quote ? <q>{d.text}</q> : <span>{d.text}</span>;
}

function Source({ d }: { d: Definition }) {
  return (
    <span className="atlas-src">
      {d.quote ? "Source" : "After"}:{" "}
      {d.url ? (
        <a href={d.url} target="_blank" rel="noreferrer noopener">
          {d.source} <ExternalLink size={11} />
        </a>
      ) : (
        d.source
      )}
    </span>
  );
}

function Definitions({ defs }: { defs: Definition[] }) {
  const [first, ...rest] = defs;
  return (
    <section className="atlas-defs" aria-label="Reference definitions">
      <h3>
        <Quote size={14} /> Reference definitions
      </h3>
      <dl>
        {[first, ...rest].map((d, k) => (
          <div key={d.term} id={"def-" + slug(d.term)} className={"atlas-def" + (k === 0 ? " lead" : "")}>
            <dt>{d.term}</dt>
            <dd>
              <DefText d={d} />
              <Source d={d} />
              {d.note && <small className="atlas-def-note">{d.note}</small>}
            </dd>
          </div>
        ))}
      </dl>
      <p className="atlas-defs-key">Text in quotation marks is the source's own wording; the others are faithful paraphrases of the cited source.</p>
    </section>
  );
}

function Glossary({ go }: { go: (id: string) => void }) {
  const [q, setQ] = useState("");
  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? GLOSSARY.filter((d) => (d.term + " " + d.text).toLowerCase().includes(s)) : GLOSSARY;
  }, [q]);
  return (
    <section className="atlas-glossary">
      <div className="atlas-glossary-head">
        <h2>Glossary</h2>
        <input type="search" placeholder="Search terms…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search the glossary" />
      </div>
      <dl>
        {items.map((d) => {
          const c = conceptById(d.concept)!;
          const r = REGIONS.find((x) => x.id === c.region)!;
          return (
            <div key={d.concept + d.term} className="atlas-def" style={{ ["--rc" as any]: r.color }}>
              <dt>{d.term}</dt>
              <dd>
                <DefText d={d} />
                <Source d={d} />
                <button className="atlas-gl-go" onClick={() => go(d.concept)}>
                  {c.title} <ArrowRight size={12} />
                </button>
              </dd>
            </div>
          );
        })}
        {items.length === 0 && <p className="atlas-defs-key">No term matches “{q}”.</p>}
      </dl>
    </section>
  );
}

/* ---------- figures: real data where we have it (URDF), labelled illustrations elsewhere ---------- */

type Meta = { title: string; caption: string; data?: string };
const META: Record<Visual, Meta> = {
  "sense-act": { title: "The sense-decide-act loop", caption: "Every Physical AI system, from a robot arm to a car, runs this loop continuously." },
  "ai-kinds": { title: "Generative AI vs Physical AI", caption: "Same family of models; different inputs, outputs and consequences." },
  "arm-explore": { title: "The ALOHA follower arm", caption: "", data: "3D model from the vendor URDF" },
  chain: { title: "The arm as a kinematic chain", caption: "Six revolute joints carry the gripper; the gripper fingers slide (prismatic joint). Axis of each joint as declared in the URDF.", data: "vendor URDF" },
  "arm-swing": { title: "Forward kinematics in 3D", caption: "The elbow swings ±0.32 rad around the ALOHA start pose; every frame is computed by forward kinematics from the URDF.", data: "vendor URDF" },
  "planar-fk": { title: "Try it: forward kinematics, side view", caption: "Shoulder and elbow of the ViperX 300 S seen from the side (waist and twists at zero). Link lengths and joint limits are the URDF values; the dots show every wrist position the two limits allow.", data: "vendor URDF" },
  "joint-limits": { title: "Joint limits of the follower arm", caption: "Allowed range of each joint (shaded), read from the <limit> element of each URDF joint.", data: "vendor URDF" },
  "servo-loop": { title: "A servo feedback loop", caption: "The controller acts on the error between target and measured angle." },
  gains: { title: "What the gains change", caption: "Qualitative sketch of typical responses to a step in the target, not a simulation result. Real curves for each joint come from OpenModelica runs in Joint simulation." },
  effort: { title: "Maximum effort per joint", caption: "The effort attribute of each joint's URDF <limit> (N·m). The joints nearest the base carry the rest of the arm and are given the largest values.", data: "vendor URDF" },
  twin: { title: "Animation vs physics model", caption: "An animation replays; a model computes - so it can answer “what if?”." },
  "twin-levels": { title: "Model, shadow, twin", caption: "The three levels of Kritzinger et al. (2018), told apart by how data flows between the real object and its digital counterpart." },
  "modelica-1d": { title: "A 1D model of one joint", caption: "The structure of the studio's Joint simulation model (kkh/studio/servo1d.py); the equation is its torque balance." },
  acausal: { title: "Signals vs physical connections", caption: "In a block diagram you decide what is input and output; in Modelica you connect parts and the tool sorts the equations." },
  scoring: { title: "Two scorecards", caption: "Left: how a generated model is measured. Right: how a review of that model is measured against known problems." },
  "three-ways": { title: "Three methods, one set of checks", caption: "What the Convert & compare page runs. The checks are real OpenModelica runs compared with the URDF; no method sees the expected answer." },
  tools: { title: "One language, several tools", caption: "Modelica models are text; tools compile and simulate them. Dymola has not been tested with the studio's package." },
  provenance: { title: "Four labels for every number", caption: "Used across the studio for every parameter and result." },
  "prov-o": { title: "Provenance of the follower URDF, in PROV terms", caption: "A real chain from this repository (data/urdf/expansion_record.json): the pinned vendor file, the expansion run, and the file the studio reads. PROV drawing convention: entities as ovals, activities as rectangles, agents as pentagons.", data: "repository record" },
  "leader-follower": { title: "Teleoperation with leader and follower", caption: "The person moves the leader; the follower mirrors it and everything is recorded." },
  "lfd-pipeline": { title: "From demonstrations to a policy", caption: "The usual imitation-learning pipeline, and the part the studio covers today." },
  chunking: { title: "Action chunking (ACT)", caption: "Instead of one action per decision, ACT predicts a chunk of k future actions at each decision." },
  grounding: { title: "Answering with grounding", caption: "Grounding gives the model the facts it needs before it answers." },
  rag: { title: "How a grounded answer is built", caption: "Retrieval-augmented generation as used by the studio, with the model running locally." },
  "fm-outputs": { title: "Two ways a robot AI can give orders", caption: "Joint angles drive one known arm directly. Gripper poses fit any two-armed robot, but need inverse kinematics and limit checks on the way to the motors: the part the studio's engineering model can check." },
  "bench-vs-studio": { title: "What a benchmark measures, and what the studio measures", caption: "A benchmark scores the robot's AI on tasks. The studio checks the robot model the AI runs on. Different questions, both needed before trusting a robot." },
  sim2real: { title: "The sim-to-real gap in this studio", caption: "What the current model does not capture." },
  "close-gap": { title: "Closing the gap, one parameter at a time", caption: "The loop that turns an assumed value into a measured one." },
  vv: { title: "Verification vs validation", caption: "Two different questions; the studio answers the first today, the second needs the real robot." },
};

function Figure({ v }: { v: Visual }) {
  const m = META[v];
  return (
    <figure className="atlas-fig">
      <header className="atlas-fig-head">
        <b>{m.title}</b>
        <span className={"atlas-fig-kind" + (m.data ? " data" : "")}>{m.data ? "Real data · " + m.data : "Illustration"}</span>
      </header>
      <ConceptVisual v={v} />
      {m.caption && <figcaption>{m.caption}</figcaption>}
    </figure>
  );
}

function ConceptVisual({ v }: { v: Visual }) {
  switch (v) {
    case "arm-explore":
      return <ArmExplore />;
    case "arm-swing":
      return <ArmView focus="elbow" mode="simulate" theme="light" height={260} autoRotate={false} />;
    case "planar-fk":
      return <PlanarFK />;
    default:
      return <>{DIAGRAMS[v]}</>;
  }
}

function ArmExplore() {
  const [hover, setHover] = useState<Part>(),
    [focus, setFocus] = useState("shoulder");
  const shown = hover || PARTS.find((p) => p.joint === focus)!;
  return (
    <>
      <ArmView focus={shown.joint} mode="robot" theme="light" height={260} onSelect={setFocus} onHover={setHover} />
      <div className="atlas-parts">
        {PARTS.map((p) => (
          <button key={p.joint} className={p.joint === shown.joint ? "on" : ""} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(undefined)} onClick={() => setFocus(p.joint)}>
            {p.name}
          </button>
        ))}
      </div>
      <p className="atlas-part-note">
        <b>{shown.name}</b> - {shown.plain}
      </p>
    </>
  );
}

/* ViperX 300 S values from data/urdf/aloha_vx300s.urdf (expanded from the pinned Interbotix xacro). */
const VX = {
  shoulderZ: 0.079 + 0.04805, // waist origin z + shoulder origin z (m)
  upper: [0.05955, 0.3] as const, // elbow origin in the upper-arm frame (x, z) (m)
  fore: 0.2 + 0.1, // forearm_roll origin x + wrist_angle origin x (m)
  limits: [
    { joint: "waist", name: "Base rotation", lo: -3.141582653589793, hi: 3.141582653589793, effort: 10 },
    { joint: "shoulder", name: "Shoulder", lo: -1.8500490071139892, hi: 1.2566370614359172, effort: 20 },
    { joint: "elbow", name: "Elbow", lo: -1.7627825445142729, hi: 1.6057029118347832, effort: 15 },
    { joint: "forearm_roll", name: "Forearm twist", lo: -3.141582653589793, hi: 3.141582653589793, effort: 2 },
    { joint: "wrist_angle", name: "Wrist", lo: -1.8675022996339325, hi: 2.234021442552742, effort: 5 },
    { joint: "wrist_rotate", name: "Wrist twist", lo: -3.141582653589793, hi: 3.141582653589793, effort: 1 },
  ],
  finger: { lo: 0.021, hi: 0.057, effort: 5 },
};
const deg = (r: number) => (r * 180) / Math.PI;

/** Rotation about the URDF y axis, applied to an (x, z) vector. */
const roty = (t: number, x: number, z: number): [number, number] => [x * Math.cos(t) + z * Math.sin(t), -x * Math.sin(t) + z * Math.cos(t)];
function fk(q1: number, q2: number) {
  const [ex, ez] = roty(q1, VX.upper[0], VX.upper[1]);
  const elbow: [number, number] = [ex, VX.shoulderZ + ez];
  const [wx, wz] = roty(q1 + q2, VX.fore, 0);
  return { elbow, wrist: [elbow[0] + wx, elbow[1] + wz] as [number, number] };
}

function PlanarFK() {
  const [S, E] = [VX.limits[1], VX.limits[2]];
  const [q1, setQ1] = useState(0),
    [q2, setQ2] = useState(0);
  const cloud = useMemo(() => {
    const pts: [number, number][] = [];
    for (let a = 0; a <= 36; a++) for (let b = 0; b <= 36; b++) pts.push(fk(S.lo + ((S.hi - S.lo) * a) / 36, E.lo + ((E.hi - E.lo) * b) / 36).wrist);
    return pts;
  }, [S, E]);
  const { elbow, wrist } = fk(q1, q2);
  // metres → svg: x ∈ [-0.7, 0.75], z ∈ [-0.55, 0.8]
  const k = 230,
    X = (x: number) => 20 + (x + 0.7) * k,
    Z = (z: number) => 20 + (0.8 - z) * k;
  const W = 20 + 1.45 * k + 20,
    H = 20 + 1.35 * k + 20;
  const f = (n: number) => n.toFixed(3);
  return (
    <div className="atlas-fk">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Side view of the shoulder and elbow" className="atlas-svg fk">
        <rect x={X(-0.7)} y={Z(0)} width={1.45 * k} height={0.55 * k} fill="#f1f5f9" />
        <line x1={X(-0.7)} x2={X(0.75)} y1={Z(0)} y2={Z(0)} stroke={line} strokeWidth={1.5} />
        <text x={X(0.73)} y={Z(0) + 16} textAnchor="end" fontSize={11} fill={muted}>
          table (z = 0)
        </text>
        {cloud.map(([x, z], n) => (
          <circle key={n} cx={X(x)} cy={Z(z)} r={1.6} fill={z < 0 ? "#f2b8b2" : "#bfd0fb"} />
        ))}
        <rect x={X(-0.05)} y={Z(VX.shoulderZ)} width={0.1 * k} height={VX.shoulderZ * k} rx={4} fill="#e2e8f0" stroke={line} />
        <line x1={X(0)} y1={Z(VX.shoulderZ)} x2={X(elbow[0])} y2={Z(elbow[1])} stroke={ink} strokeWidth={9} strokeLinecap="round" />
        <line x1={X(elbow[0])} y1={Z(elbow[1])} x2={X(wrist[0])} y2={Z(wrist[1])} stroke="#0f766e" strokeWidth={8} strokeLinecap="round" />
        <circle cx={X(0)} cy={Z(VX.shoulderZ)} r={7} fill="#fff" stroke={blue} strokeWidth={2.5} />
        <circle cx={X(elbow[0])} cy={Z(elbow[1])} r={7} fill="#fff" stroke={blue} strokeWidth={2.5} />
        <circle cx={X(wrist[0])} cy={Z(wrist[1])} r={6} fill={blue} />
        <text x={X(wrist[0]) + 10} y={Z(wrist[1]) - 8} fontSize={12} fontWeight={650} fill={blue}>
          wrist ({f(wrist[0])}, {f(wrist[1])}) m
        </text>
        <text x={X(0) - 12} y={Z(VX.shoulderZ) + 4} textAnchor="end" fontSize={11} fill={muted}>
          shoulder
        </text>
        <text x={X(elbow[0]) - 12} y={Z(elbow[1]) - 6} textAnchor="end" fontSize={11} fill={muted}>
          elbow
        </text>
      </svg>
      <div className="atlas-fk-ctl">
        {[
          { label: "Shoulder q₁", v: q1, set: setQ1, j: S },
          { label: "Elbow q₂", v: q2, set: setQ2, j: E },
        ].map((s) => (
          <label key={s.label}>
            <span>
              {s.label} <b>{deg(s.v).toFixed(0)}°</b>
            </span>
            <input type="range" min={s.j.lo} max={s.j.hi} step={0.01} value={s.v} onChange={(e) => s.set(+e.target.value)} />
            <small>
              limit {deg(s.j.lo).toFixed(0)}° … {deg(s.j.hi).toFixed(0)}°
            </small>
          </label>
        ))}
        <div className="atlas-fk-eq">
          <small>Forward kinematics of this chain (URDF lengths in metres)</small>
          <code>x = 0.0596·cos q₁ + 0.300·sin q₁ + 0.300·cos(q₁+q₂)</code>
          <code>z = 0.127 − 0.0596·sin q₁ + 0.300·cos q₁ − 0.300·sin(q₁+q₂)</code>
        </div>
        <p className="atlas-fk-legend">
          <i style={{ background: "#bfd0fb" }} /> reachable wrist positions <i style={{ background: "#f2b8b2" }} /> allowed by the joint limits, but below the table
        </p>
        <button
          className="atlas-fk-reset"
          onClick={() => {
            setQ1(0);
            setQ2(0);
          }}
        >
          Reset to zero
        </button>
      </div>
    </div>
  );
}

/* ---------- static diagrams (illustrations, no data unless labelled) ---------- */

const ink = "#0f1d33",
  muted = "#64748b",
  line = "#c9d3e0",
  blue = "#1d4ed8",
  blueBg = "#e8efff",
  blueLine = "#bfd0fb",
  green = "#0f7a4f",
  greenBg = "#e3f4ec",
  amber = "#a15c07",
  amberBg = "#fdf1dc",
  red = "#b42318",
  redBg = "#fdecea",
  violet = "#5b3fb6",
  violetBg = "#eeeafc";
const Box = ({ x, y, w, h, t, s, fill = "#fff", stroke = line, color = ink, fs = 14 }: { x: number; y: number; w: number; h: number; t: string; s?: string; fill?: string; stroke?: string; color?: string; fs?: number }) => (
  <g>
    <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.4} />
    <text x={x + w / 2} y={y + h / 2 + (s ? -4 : 5)} textAnchor="middle" fontSize={fs} fontWeight={650} fill={color}>
      {t}
    </text>
    {s && (
      <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" fontSize={11.5} fill={muted}>
        {s}
      </text>
    )}
  </g>
);
const T = ({ x, y, children, a = "middle", s = 12, c = muted, w }: { x: number; y: number; children: React.ReactNode; a?: "start" | "middle" | "end"; s?: number; c?: string; w?: number }) => (
  <text x={x} y={y} textAnchor={a} fontSize={s} fill={c} fontWeight={w}>
    {children}
  </text>
);
const Arrow = ({ d, color = muted, dash }: { d: string; color?: string; dash?: boolean }) => (
  <path d={d} fill="none" stroke={color} strokeWidth={1.8} markerEnd="url(#atl-arrow)" strokeDasharray={dash ? "5 4" : undefined} />
);
const Defs = () => (
  <defs>
    <marker id="atl-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M0 0 L10 5 L0 10 z" fill={muted} />
    </marker>
  </defs>
);
const Svg = ({ h = 220, children, label }: { h?: number; children: React.ReactNode; label: string }) => (
  <svg viewBox={`0 0 640 ${h}`} role="img" aria-label={label} className="atlas-svg">
    <Defs />
    {children}
  </svg>
);

/** Dial showing an allowed angular range (0 at the top, positive clockwise in the drawing). */
function Dial({ cx, cy, r, lo, hi }: { cx: number; cy: number; r: number; lo: number; hi: number }) {
  const p = (a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  const full = hi - lo > 2 * Math.PI - 0.01;
  const [x0, y0] = p(lo),
    [x1, y1] = p(hi);
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} fill="#fff" stroke={line} strokeWidth={1.2} />
      {full ? <circle cx={cx} cy={cy} r={r} fill="#d6f0ea" stroke="#0f766e" strokeWidth={1.4} /> : <path d={`M${cx} ${cy} L${x0} ${y0} A${r} ${r} 0 ${hi - lo > Math.PI ? 1 : 0} 1 ${x1} ${y1} Z`} fill="#d6f0ea" stroke="#0f766e" strokeWidth={1.4} />}
      <line x1={cx} y1={cy} x2={cx} y2={cy - r} stroke={ink} strokeWidth={1.4} strokeDasharray="3 3" />
      <circle cx={cx} cy={cy} r={2.5} fill={ink} />
    </g>
  );
}

const DIAGRAMS: Partial<Record<Visual, React.ReactNode>> = {
  "sense-act": (
    <Svg label="Sense, decide, act loop" h={210}>
      <Box x={30} y={70} w={150} h={64} t="Sense" s="cameras · encoders" />
      <Box x={245} y={70} w={150} h={64} t="Decide" s="controller · policy" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={460} y={70} w={150} h={64} t="Act" s="motors · gripper" />
      <Arrow d="M180 102 H240" />
      <Arrow d="M395 102 H455" />
      <Arrow d="M535 134 C535 190, 105 190, 105 140" />
      <T x={320} y={196}>
        the world changes - and the loop runs again, many times per second
      </T>
      <T x={320} y={40} s={12.5}>
        physics everywhere: inertia, gravity, friction, limits
      </T>
    </Svg>
  ),
  "ai-kinds": (
    <Svg label="Generative AI compared with Physical AI" h={250}>
      <T x={20} y={34} a="start" s={12.5} w={700} c={muted}>
        GENERATIVE AI
      </T>
      <Box x={20} y={44} w={170} h={56} t="Text, images" s="a prompt" />
      <Box x={235} y={44} w={170} h={56} t="Model" s="language / image model" fill={violetBg} stroke="#cfc4f5" color={violet} />
      <Box x={450} y={44} w={170} h={56} t="Text, images" s="an answer you can edit" />
      <Arrow d="M190 72 H231" />
      <Arrow d="M405 72 H446" />
      <T x={20} y={140} a="start" s={12.5} w={700} c={blue}>
        PHYSICAL AI
      </T>
      <Box x={20} y={150} w={170} h={56} t="Sensors" s="cameras · joint angles" />
      <Box x={235} y={150} w={170} h={56} t="Policy / controller" s="decides the next move" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={450} y={150} w={170} h={56} t="Motor commands" s="move mass in the world" fill={redBg} stroke="#f2b8b2" color={red} />
      <Arrow d="M190 178 H231" />
      <Arrow d="M405 178 H446" />
      <Arrow d="M535 206 C535 240, 105 240, 105 210" />
      <T x={320} y={244} s={11.5}>
        the action changes what the sensors see next - a closed loop, with physical consequences
      </T>
    </Svg>
  ),
  chain: (
    <Svg label="Kinematic chain of the follower arm" h={210}>
      <rect x={14} y={120} width={58} height={34} rx={4} fill="#e2e8f0" stroke={line} />
      <path d="M10 160 H76" stroke={muted} strokeWidth={2} />
      {[0, 1, 2, 3, 4, 5, 6].map((n) => (
        <line key={n} x1={14 + n * 9} y1={160} x2={8 + n * 9} y2={168} stroke={muted} strokeWidth={1.2} />
      ))}
      <T x={43} y={186} s={11}>
        base
      </T>
      {[
        ["Base rotation", "about z", false],
        ["Shoulder", "about y · ×2 motors", false],
        ["Elbow", "about y · ×2 motors", false],
        ["Forearm twist", "about x", false],
        ["Wrist", "about y", false],
        ["Wrist twist", "about x", false],
        ["Gripper", "fingers slide", true],
      ].map(([name, ax, prism], n) => {
        const x = 104 + n * 78;
        return (
          <g key={name as string}>
            <line x1={x - 32} y1={137} x2={x - 12} y2={137} stroke={ink} strokeWidth={6} strokeLinecap="round" />
            {prism ? <rect x={x - 11} y={126} width={22} height={22} rx={3} fill="#fff" stroke="#0f766e" strokeWidth={2.4} /> : <circle cx={x} cy={137} r={11} fill="#fff" stroke={blue} strokeWidth={2.4} />}
            <T x={x} y={n % 2 ? 176 : 104} s={12} c={ink} w={650}>
              {name}
            </T>
            <T x={x} y={n % 2 ? 192 : 88} s={10.5}>
              {ax}
            </T>
          </g>
        );
      })}
      <T x={320} y={30} s={12.5}>
        links (bars) joined by joints: ○ revolute (turns) · □ prismatic (slides)
      </T>
    </Svg>
  ),
  "joint-limits": (
    <Svg label="Allowed range of each joint" h={250}>
      {VX.limits.map((j, n) => {
        const cx = 60 + n * 104;
        return (
          <g key={j.joint}>
            <Dial cx={cx} cy={90} r={38} lo={j.lo} hi={j.hi} />
            <T x={cx} y={152} s={12.5} c={ink} w={650}>
              {j.name}
            </T>
            <T x={cx} y={170} s={11.5}>
              {deg(j.lo).toFixed(0)}° … {deg(j.hi).toFixed(0)}°
            </T>
          </g>
        );
      })}
      <rect x={160} y={200} width={320} height={10} rx={5} fill="#f1f5f9" stroke={line} />
      <rect x={160 + (VX.finger.lo / 0.06) * 320} y={200} width={((VX.finger.hi - VX.finger.lo) / 0.06) * 320} height={10} rx={5} fill="#d6f0ea" stroke="#0f766e" />
      <T x={150} y={209} a="end" s={12} c={ink} w={650}>
        Gripper finger
      </T>
      <T x={490} y={209} a="start" s={11.5}>
        {(VX.finger.lo * 1000).toFixed(0)} … {(VX.finger.hi * 1000).toFixed(0)} mm
      </T>
      <T x={320} y={238} s={11}>
        dashed line = 0 (the URDF zero position); ±180° joints can turn almost a full circle
      </T>
    </Svg>
  ),
  "servo-loop": (
    <Svg label="Servo feedback loop" h={220}>
      <Box x={20} y={70} w={110} h={58} t="Target" s="angle wanted" />
      <circle cx={175} cy={99} r={16} fill="#fff" stroke={line} strokeWidth={1.4} />
      <T x={175} y={104} s={15} c={ink}>
        −
      </T>
      <Box x={225} y={66} w={130} h={66} t="Controller" s="kp · error, kd · speed" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={395} y={66} w={100} h={66} t="Motor" s="torque (limited)" />
      <Box x={530} y={66} w={95} h={66} t="Joint" s="inertia, gravity" />
      <Arrow d="M130 99 H157" />
      <Arrow d="M191 99 H221" />
      <Arrow d="M355 99 H391" />
      <Arrow d="M495 99 H526" />
      <Arrow d="M577 132 V180 H175 V118" />
      <T x={380} y={198}>
        sensor: actual angle, fed back
      </T>
      <T x={203} y={88} s={11}>
        error
      </T>
    </Svg>
  ),
  gains: (
    <Svg label="Qualitative sketch of step responses" h={240}>
      <line x1={60} y1={200} x2={610} y2={200} stroke={line} strokeWidth={1.4} />
      <line x1={60} y1={30} x2={60} y2={200} stroke={line} strokeWidth={1.4} />
      <T x={610} y={218} a="end" s={11}>
        time →
      </T>
      <T x={52} y={36} a="end" s={11}>
        angle
      </T>
      <line x1={60} y1={70} x2={610} y2={70} stroke={ink} strokeWidth={1.2} strokeDasharray="5 4" />
      <T x={606} y={62} a="end" s={11} c={ink}>
        target
      </T>
      <path d="M60 200 C 110 200, 120 26, 160 34 S 200 92, 232 80 S 270 60, 300 68 S 350 72, 610 70" fill="none" stroke={red} strokeWidth={2.4} />
      <path d="M60 200 C 120 200, 150 72, 230 70 L 610 70" fill="none" stroke={green} strokeWidth={2.6} />
      <path d="M60 200 C 220 200, 330 100, 610 78" fill="none" stroke={amber} strokeWidth={2.4} />
      <T x={170} y={24} a="start" s={12} c={red} w={650}>
        too stiff: overshoots and rings
      </T>
      <T x={250} y={98} a="start" s={12} c={green} w={650}>
        well tuned: fast, little overshoot
      </T>
      <T x={360} y={150} a="start" s={12} c={amber} w={650}>
        too soft: smooth but lags behind
      </T>
    </Svg>
  ),
  effort: (
    <Svg label="Maximum effort per joint from the URDF" h={230}>
      {VX.limits.map((j, n) => (
        <g key={j.joint} transform={`translate(0 ${24 + n * 32})`}>
          <T x={130} y={16} a="end" s={12.5} c={ink} w={600}>
            {j.name}
          </T>
          <rect x={142} y={3} width={(j.effort / 20) * 400} height={18} rx={4} fill={n === 1 || n === 2 ? "#0369a1" : "#7dd3fc"} />
          <T x={150 + (j.effort / 20) * 400} y={16} a="start" s={12} c={ink}>
            {j.effort} N·m
          </T>
        </g>
      ))}
      <T x={320} y={222} s={11}>
        darker: the two joints driven by two motors each
      </T>
    </Svg>
  ),
  twin: (
    <Svg label="Animation versus physics model" h={230}>
      <T x={160} y={30} s={13} w={650}>
        ANIMATION
      </T>
      <T x={480} y={30} s={13} w={650} c={blue}>
        PHYSICS MODEL
      </T>
      <Box x={60} y={50} w={200} h={52} t="Positions over time" s="given by someone" />
      <Arrow d="M160 102 V130" />
      <Box x={60} y={134} w={200} h={52} t="Moving picture" s="no 'why', no 'what if'" />
      <Box x={370} y={44} w={220} h={46} t="Masses · axes · motors" s="+ a setting to try" fill={blueBg} stroke={blueLine} color={blue} />
      <Arrow d="M480 90 V112" />
      <Box x={370} y={116} w={220} h={40} t="Equations of motion, solved" />
      <Arrow d="M480 156 V172" />
      <Box x={370} y={176} w={220} h={44} t="Angles · torques · errors" s="change one input, run again" />
      <line x1={320} y1={44} x2={320} y2={214} stroke={line} strokeDasharray="4 5" />
    </Svg>
  ),
  "twin-levels": (
    <Svg label="Digital model, digital shadow and digital twin" h={260}>
      {[
        { t: "Digital model", p2d: "by hand", d2p: "by hand", today: true },
        { t: "Digital shadow", p2d: "automatic", d2p: "by hand" },
        { t: "Digital twin", p2d: "automatic", d2p: "automatic" },
      ].map((L, n) => {
        const x = 20 + n * 210;
        return (
          <g key={L.t}>
            <rect x={x} y={20} width={190} height={196} rx={12} fill={L.today ? "#f8fafc" : "#fff"} stroke={L.today ? blue : line} strokeWidth={L.today ? 1.8 : 1.2} />
            <T x={x + 95} y={44} s={14} c={ink} w={700}>
              {L.t}
            </T>
            <Box x={x + 25} y={58} w={140} h={40} t="Digital object" fill={blueBg} stroke={blueLine} color={blue} fs={13} />
            <Box x={x + 25} y={160} w={140} h={40} t="Real object" fs={13} />
            <Arrow d={`M${x + 70} 156 V102`} dash={L.p2d === "by hand"} />
            <Arrow d={`M${x + 120} 102 V156`} dash={L.d2p === "by hand"} />
            <T x={x + 64} y={134} a="end" s={10.5}>
              {L.p2d}
            </T>
            <T x={x + 126} y={134} a="start" s={10.5}>
              {L.d2p}
            </T>
          </g>
        );
      })}
      <T x={115} y={238} s={12} c={blue} w={650}>
        ▲ the studio today
      </T>
      <T x={430} y={238} s={11.5}>
        dashed = manual data flow · solid = automatic
      </T>
    </Svg>
  ),
  "modelica-1d": (
    <Svg label="A one-dimensional joint model as connected components" h={250}>
      <Box x={14} y={60} w={108} h={58} t="Servo" s="PD · limit · lag" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={150} y={60} w={100} h={58} t="Torque" s="motor output" />
      <Box x={278} y={60} w={100} h={58} t="Inertia J" s="moving arm" />
      <Box x={406} y={60} w={100} h={58} t="Damper" s="URDF damping" />
      <Box x={534} y={60} w={94} h={58} t="Load" s="gravity · friction" />
      {[122, 250, 378, 506].map((x) => (
        <g key={x}>
          <line x1={x} y1={89} x2={x + 28} y2={89} stroke={ink} strokeWidth={3} />
          <circle cx={x + 14} cy={89} r={4} fill="#fff" stroke={ink} strokeWidth={1.5} />
        </g>
      ))}
      <Arrow d="M328 118 V150 H68 V122" dash />
      <T x={198} y={166} s={11.5}>
        measured angle and speed fed back
      </T>
      <T x={320} y={36} s={12.5}>
        components connected like real parts - the tool derives and solves the equations
      </T>
      <rect x={120} y={190} width={400} height={42} rx={10} fill="#f8fafc" stroke={line} />
      <text x={320} y={216} textAnchor="middle" fontSize={14} fill={ink} fontFamily="Cambria, Georgia, serif" fontStyle="italic">
        J·q̈ = τ_motor − d·q̇ − A·sin(q+φ) − τ_friction
      </text>
    </Svg>
  ),
  acausal: (
    <Svg label="Causal block diagram versus acausal Modelica connection" h={250}>
      <T x={160} y={28} s={13} w={650}>
        BLOCK DIAGRAM (causal)
      </T>
      <T x={480} y={28} s={13} w={650} c={blue}>
        MODELICA (acausal)
      </T>
      <Box x={20} y={60} w={70} h={44} t="τ" fs={15} />
      <Box x={120} y={60} w={70} h={44} t="1/J" fs={14} />
      <Box x={220} y={60} w={70} h={44} t="∫∫" fs={15} />
      <Arrow d="M90 82 H116" />
      <Arrow d="M190 82 H216" />
      <Arrow d="M290 82 H306" />
      <T x={300} y={70} a="end" s={11}>
        q
      </T>
      <T x={160} y={140} s={11.5}>
        you choose the direction of every signal:
      </T>
      <T x={160} y={156} s={11.5}>
        torque in, angle out. To ask the reverse
      </T>
      <T x={160} y={172} s={11.5}>
        question, you redraw the diagram.
      </T>
      <line x1={320} y1={40} x2={320} y2={230} stroke={line} strokeDasharray="4 5" />
      <Box x={345} y={60} w={80} h={44} t="Motor" fs={13} fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={445} y={60} w={80} h={44} t="Gear" fs={13} />
      <Box x={545} y={60} w={80} h={44} t="Inertia" fs={13} />
      {[425, 525].map((x) => (
        <g key={x}>
          <line x1={x} y1={82} x2={x + 20} y2={82} stroke={ink} strokeWidth={3} />
          <circle cx={x + 10} cy={82} r={4} fill="#fff" stroke={ink} strokeWidth={1.5} />
        </g>
      ))}
      <T x={485} y={140} s={11.5}>
        you connect parts like the real machine;
      </T>
      <T x={485} y={156} s={11.5}>
        each connection means "same angle, torques
      </T>
      <T x={485} y={172} s={11.5}>
        balance". The tool sorts the equations.
      </T>
      <rect x={360} y={192} width={250} height={34} rx={8} fill="#f8fafc" stroke={line} />
      <text x={485} y={214} textAnchor="middle" fontSize={13} fill={ink} fontFamily="Consolas, monospace">
        connect(motor.flange, gear.flange_a);
      </text>
    </Svg>
  ),
  tools: (
    <Svg label="Modelica language, library and tools" h={260}>
      <Box x={110} y={20} w={200} h={52} t="Modelica language" s="open specification" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={330} y={20} w={200} h={52} t="Standard Library" s="mechanics, electrics, control…" fill={blueBg} stroke={blueLine} color={blue} />
      <Arrow d="M220 72 L130 116" />
      <Arrow d="M320 72 V116" />
      <Arrow d="M420 72 L510 116" />
      <Box x={20} y={120} w={200} h={58} t="OpenModelica" s="open-source · used by this studio" fill={greenBg} stroke="#bfe3cf" color={green} />
      <Box x={230} y={120} w={180} h={58} t="Dymola" s="commercial · Dassault Systèmes" />
      <Box x={420} y={120} w={200} h={58} t="Other Modelica tools" s="commercial and open-source" />
      <Arrow d="M320 178 V200" />
      <Box x={170} y={204} w={300} h={44} t="FMU (FMI standard)" s="export a model to run in other simulators" />
    </Svg>
  ),
  scoring: (
    <Svg label="How models and reviews are scored" h={300}>
      <T x={160} y={24} s={13} w={700} c={blue}>
        A MODEL
      </T>
      <T x={480} y={24} s={13} w={700} c={violet}>
        A REVIEW
      </T>
      {[
        ["Reads · complete · runs", "OpenModelica"],
        ["Structure", "all parts and joints"],
        ["Geometry", "every joint driven, vs robot file"],
        ["Parameters", "axes, masses, inertias"],
        ["Dynamics", "torques vs MuJoCo"],
      ].map(([t, s2], k) => (
        <Box key={t} x={40} y={36 + k * 50} w={240} h={42} t={t} s={s2} fs={12.5} fill={k === 4 ? greenBg : blueBg} stroke={k === 4 ? "#bfe3cf" : blueLine} color={k === 4 ? green : blue} />
      ))}
      {[
        ["Recall · precision", "known problems found, false alarms"],
        ["Corrections that work", "fix applied to a copy, re-checked"],
        ["Facts stated correctly", "quoted numbers vs robot file"],
        ["Calibration", "Brier score of the confidence"],
        ["Time", "AI seconds or human minutes"],
      ].map(([t, s2], k) => (
        <Box key={t} x={360} y={36 + k * 50} w={250} h={42} t={t} s={s2} fs={12.5} fill={violetBg} stroke="#cfc4f5" color={violet} />
      ))}
      <line x1={320} y1={36} x2={320} y2={280} stroke={line} strokeDasharray="4 5" />
      <T x={320} y={296} s={11}>
        every number is measured; none is judged by an AI
      </T>
    </Svg>
  ),
  "three-ways": (
    <Svg label="Three conversion methods judged by the same checks" h={270}>
      <Box x={14} y={108} w={110} h={54} t="URDF file" s="the robot" />
      <Arrow d="M124 135 C 150 135, 150 52, 176 52" />
      <Arrow d="M124 135 H176" />
      <Arrow d="M124 135 C 150 135, 150 218, 176 218" />
      <Box x={180} y={26} w={190} h={52} t="1 · AI only" s="local language model" fill={violetBg} stroke="#cfc4f5" color={violet} fs={13} />
      <Box x={180} y={109} w={190} h={52} t="2 · AI + library search" s="BM25 over the Modelica library" fill={blueBg} stroke={blueLine} color={blue} fs={13} />
      <Box x={180} y={192} w={190} h={52} t="3 · URDFModelica" s="rule-based converter (DLR)" fill={greenBg} stroke="#bfe3cf" color={green} fs={13} />
      <Arrow d="M370 52 C 400 52, 400 135, 428 135" />
      <Arrow d="M370 135 H428" />
      <Arrow d="M370 218 C 400 218, 400 135, 428 135" />
      <rect x={432} y={40} width={196} height={190} rx={12} fill="#fff" stroke={line} />
      <T x={530} y={62} s={12.5} c={ink} w={700}>
        The same 7 checks
      </T>
      {["file produced", "OpenModelica reads it", "complete model", "it runs", "all parts and joints", "geometry matches URDF", "axes and masses right"].map((t, k) => (
        <T key={t} x={448} y={86 + k * 20} a="start" s={11.5}>
          {k + 1}. {t}
        </T>
      ))}
      <T x={320} y={262} s={11}>
        AI methods: same model, settings and two repair rounds with OpenModelica's messages; no method sees the expected answer
      </T>
    </Svg>
  ),
  provenance: (
    <Svg label="Provenance labels" h={200}>
      {[
        ["VERIFIED", "from a pinned source file", green, greenBg],
        ["DERIVED", "computed by a stated method", "#0369a1", "#e0f2fe"],
        ["ASSUMED", "chosen, not measured - tunable", amber, amberBg],
        ["SIMULATED", "output of a real OpenModelica run", blue, blueBg],
      ].map(([t, s, c, bg], k) => (
        <g key={t} transform={`translate(${30 + (k % 2) * 300} ${30 + Math.floor(k / 2) * 80})`}>
          <rect width={280} height={60} rx={10} fill={bg} stroke={c} strokeOpacity={0.35} />
          <text x={16} y={26} fontSize={13} fontWeight={700} letterSpacing={1} fill={c}>
            {t}
          </text>
          <text x={16} y={46} fontSize={12} fill={ink}>
            {s}
          </text>
        </g>
      ))}
    </Svg>
  ),
  "prov-o": (
    <Svg label="PROV graph for the follower URDF" h={290}>
      <path d="M530 68 C 470 14, 170 14, 110 68" fill="none" stroke={muted} strokeWidth={1.8} markerEnd="url(#atl-arrow)" />
      <T x={320} y={30} s={10.5}>
        wasDerivedFrom
      </T>
      <ellipse cx={100} cy={100} rx={88} ry={34} fill="#fffbe6" stroke="#e0c35a" strokeWidth={1.4} />
      <T x={100} y={96} s={12} c={ink} w={650}>
        aloha_vx300s.urdf.xacro
      </T>
      <T x={100} y={113} s={10.5}>
        Interbotix · sha256 2848f3…
      </T>
      <rect x={262} y={74} width={116} height={52} rx={4} fill="#e8f1ff" stroke="#8fb0ea" strokeWidth={1.4} />
      <T x={320} y={96} s={12} c={ink} w={650}>
        xacro expansion
      </T>
      <T x={320} y={113} s={10.5}>
        activity
      </T>
      <ellipse cx={540} cy={100} rx={88} ry={34} fill="#fffbe6" stroke="#e0c35a" strokeWidth={1.4} />
      <T x={540} y={96} s={12} c={ink} w={650}>
        aloha_vx300s.urdf
      </T>
      <T x={540} y={113} s={10.5}>
        data/urdf · sha256 da63d4…
      </T>
      <Arrow d="M262 100 H192" />
      <T x={227} y={92} s={10.5}>
        used
      </T>
      <Arrow d="M452 100 H382" />
      <T x={417} y={92} s={10.5}>
        wasGeneratedBy
      </T>
      <polygon points="100,200 156,220 138,264 62,264 44,220" fill="#fdebd9" stroke="#e7a467" strokeWidth={1.4} />
      <T x={100} y={236} s={12} c={ink} w={650}>
        Trossen Robotics
      </T>
      <T x={100} y={251} s={10.5}>
        vendor
      </T>
      <polygon points="320,200 376,220 358,264 282,264 264,220" fill="#fdebd9" stroke="#e7a467" strokeWidth={1.4} />
      <T x={320} y={236} s={12} c={ink} w={650}>
        expand_xacro.py
      </T>
      <T x={320} y={251} s={10.5}>
        software agent
      </T>
      <Arrow d="M100 134 V196" />
      <T x={106} y={170} a="start" s={10.5}>
        wasAttributedTo
      </T>
      <Arrow d="M320 126 V196" />
      <T x={326} y={170} a="start" s={10.5}>
        wasAssociatedWith
      </T>
    </Svg>
  ),
  grounding: (
    <Svg label="Answer without and with grounding" h={220}>
      <Box x={30} y={30} w={270} h={52} t="Question" s="“What is the elbow's upper limit?”" />
      <Box x={340} y={30} w={270} h={52} t="Same question" s="+ retrieved facts with sources" fill={blueBg} stroke={blueLine} color={blue} />
      <Arrow d="M165 82 V112" />
      <Arrow d="M475 82 V112" />
      <Box x={30} y={116} w={270} h={56} t="Answer from memory" s="fluent - maybe invented" fill={amberBg} stroke="#f3d9a8" color={amber} />
      <Box x={340} y={116} w={270} h={56} t="Answer with citations" s="checkable against the source" fill={greenBg} stroke="#bfe3cf" color={green} />
      <T x={320} y={204}>
        either way, a person approves any change to the model
      </T>
    </Svg>
  ),
  rag: (
    <Svg label="Retrieval-augmented generation pipeline" h={250}>
      <Box x={10} y={40} w={110} h={56} t="Question" s="from the user" fs={13} />
      <Box x={140} y={40} w={150} h={56} t="Retrieve" s="Search the sources" fs={13} fill={violetBg} stroke="#cfc4f5" color={violet} />
      <Box x={310} y={40} w={150} h={56} t="Local LLM" s="Ollama · Nemotron" fs={13} fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={480} y={40} w={150} h={56} t="Answer" s="with cited facts" fs={13} fill={greenBg} stroke="#bfe3cf" color={green} />
      <Arrow d="M120 68 H136" />
      <Arrow d="M290 68 H306" />
      <Arrow d="M460 68 H476" />
      <T x={215} y={118} s={11}>
        facts + their sources
      </T>
      <T x={385} y={118} s={11}>
        prompt = question + facts
      </T>
      <Arrow d="M555 96 V146" dash />
      <Box x={330} y={150} w={300} h={52} t="If it proposes a model change" s="bounds check → OpenModelica check → human approval" fs={13} fill={amberBg} stroke="#f3d9a8" color={amber} />
      <T x={20} y={180} a="start" s={11.5}>
        nothing leaves this computer:
      </T>
      <T x={20} y={196} a="start" s={11.5}>
        graph, model and LLM all run locally
      </T>
      <T x={320} y={236} s={11}>
        the retrieval source is the project files
      </T>
    </Svg>
  ),
  "fm-outputs": (
    <Svg label="Joint-angle output versus gripper-pose output" h={290}>
      <Box x={235} y={14} w={170} h={50} t="Robot AI" s="camera + instruction" fill={violetBg} stroke="#cfc4f5" color={violet} />
      <Arrow d="M290 64 L150 96" />
      <Arrow d="M350 64 L490 96" />
      <T x={160} y={118} s={12.5} c={ink} w={700}>
        A · JOINT ANGLES
      </T>
      <T x={480} y={118} s={12.5} c={ink} w={700}>
        B · GRIPPER POSES
      </T>
      <Box x={60} y={130} w={200} h={46} t="shoulder 0.4 · elbow -0.2 …" s="one number per joint" fs={12.5} />
      <Box x={380} y={130} w={200} h={46} t="gripper here, turned so" s="same for any two-armed robot" fs={12.5} />
      <Arrow d="M160 176 V238" />
      <Arrow d="M480 176 V188" />
      <Box x={370} y={190} w={220} h={44} t="Inverse kinematics" s="done by the robot's integrator" fs={12.5} fill={amberBg} stroke="#f3d9a8" color={amber} />
      <Arrow d="M480 234 V242" />
      <Box x={60} y={242} w={520} h={36} t="Motors of one specific arm" fs={13} />
      <rect x={20} y={186} width={130} height={46} rx={8} fill={greenBg} stroke="#bfe3cf" />
      <T x={85} y={204} s={11} c={green} w={650}>
        studio check:
      </T>
      <T x={85} y={220} s={11} c={green}>
        limits · torque · speed
      </T>
      <T x={14} y={96} a="start" s={11}>
        e.g. ACT, openpi ALOHA
      </T>
      <T x={626} y={96} a="end" s={11}>
        e.g. Dream-1, GR00T
      </T>
    </Svg>
  ),
  "bench-vs-studio": (
    <Svg label="Policy benchmark compared with the studio's evidence" h={270}>
      <rect x={14} y={14} width={296} height={242} rx={12} fill="#fff" stroke={line} />
      <rect x={330} y={14} width={296} height={242} rx={12} fill="#fff" stroke={line} />
      <T x={162} y={38} s={13} c={violet} w={700}>
        POLICY BENCHMARK
      </T>
      <T x={162} y={56} s={11.5} c={ink}>
        LIBERO · RoboTwin · RoboDojo · gym-aloha
      </T>
      <Box x={36} y={70} w={252} h={44} t="Is the robot's AI good at tasks?" fs={12.5} fill={violetBg} stroke="#cfc4f5" color={violet} />
      {["same tasks, same number of tries", "score = share of tries that succeed", "vendor claim or independent?"].map((e, n) => (
        <T key={e} x={162} y={140 + n * 20} s={11.5}>
          {e}
        </T>
      ))}
      <rect x={36} y={206} width={252} height={36} rx={8} fill={redBg} />
      <T x={162} y={228} s={11.5} c={red}>
        silent about the robot model's numbers
      </T>
      <T x={478} y={38} s={13} c={green} w={700}>
        THE STUDIO'S EVIDENCE
      </T>
      <T x={478} y={56} s={11.5} c={ink}>
        about the engineering model itself
      </T>
      <Box x={352} y={70} w={252} h={44} t="Is the robot model right?" fs={12.5} fill={greenBg} stroke="#bfe3cf" color={green} />
      {[
        ["Twin validation", "model vs real recordings · being set up"],
      ].map(([t, s], n) => (
        <g key={t}>
          <T x={366} y={140 + n * 38} a="start" s={12} c={ink} w={650}>
            {t}
          </T>
          <T x={366} y={156 + n * 38} a="start" s={11}>
            {s}
          </T>
        </g>
      ))}
    </Svg>
  ),
  sim2real: (
    <Svg label="The gap between simulation and reality" h={250}>
      <Box x={30} y={30} w={210} h={60} t="Simulation" s="what the model includes" fill={blueBg} stroke={blueLine} color={blue} />
      <Box x={400} y={30} w={210} h={60} t="Real robot" s="everything, always" />
      <path d="M248 60 H392" stroke={red} strokeWidth={2} strokeDasharray="6 5" />
      <T x={320} y={50} s={13} c={red} w={700}>
        THE GAP
      </T>
      {["assumed servo gains", "backlash · flexibility", "contact & grasping", "calibration of the cell"].map((t, k) => (
        <g key={t} transform={`translate(${30 + (k % 2) * 300} ${118 + Math.floor(k / 2) * 46})`}>
          <rect width={280} height={36} rx={8} fill={redBg} stroke="#f2b8b2" />
          <T x={140} y={23} s={12.5} c={red}>
            {t}
          </T>
        </g>
      ))}
      <T x={320} y={226}>
        closed by measuring: system identification · validation runs · labelled assumptions
      </T>
    </Svg>
  ),
  "close-gap": (
    <Svg label="Loop to close the sim-to-real gap" h={280}>
      {[
        ["Measure", "real joint response", 320, 46],
        ["Identify", "fit parameters to data", 540, 120],
        ["Relabel", "assumed → derived", 470, 228],
        ["Simulate", "OpenModelica", 170, 228],
        ["Validate", "sim vs real recording", 100, 120],
      ].map(([t, s, x, y], n) => (
        <Box key={t as string} x={(x as number) - 75} y={(y as number) - 26} w={150} h={52} t={t as string} s={s as string} fs={13} fill={n === 0 ? redBg : n === 2 ? greenBg : "#fff"} stroke={n === 0 ? "#f2b8b2" : n === 2 ? "#bfe3cf" : line} color={n === 0 ? red : n === 2 ? green : ink} />
      ))}
      <Arrow d="M398 56 L480 92" />
      <Arrow d="M528 148 L500 200" />
      <Arrow d="M393 230 H250" />
      <Arrow d="M140 202 L112 148" />
      <Arrow d="M160 92 L242 56" />
      <T x={320} y={140} s={12} c={ink} w={650}>
        one parameter
      </T>
      <T x={320} y={156} s={12} c={ink} w={650}>
        at a time
      </T>
    </Svg>
  ),
  vv: (
    <Svg label="Verification versus validation" h={250}>
      {[
        { x: 20, t: "VERIFICATION", q: "Did we build the model right?", a: "Specification", b: "Model", ex: ["equations balance, model compiles", "units and bounds pass the rules"], st: "done by the studio today", c: green, bg: greenBg },
        { x: 330, t: "VALIDATION", q: "Did we build the right model?", a: "Real robot", b: "Model", ex: ["simulated vs measured motion", "for the intended use"], st: "needs the real robot - next step", c: amber, bg: amberBg },
      ].map((p) => (
        <g key={p.t}>
          <rect x={p.x} y={14} width={290} height={222} rx={12} fill="#fff" stroke={line} />
          <T x={p.x + 145} y={38} s={13} c={p.c} w={700}>
            {p.t}
          </T>
          <T x={p.x + 145} y={58} s={12.5} c={ink}>
            {p.q}
          </T>
          <Box x={p.x + 18} y={74} w={110} h={40} t={p.a} fs={12.5} />
          <Box x={p.x + 162} y={74} w={110} h={40} t={p.b} fs={12.5} fill={blueBg} stroke={blueLine} color={blue} />
          <path d={`M${p.x + 132} 94 H${p.x + 158}`} stroke={muted} strokeWidth={1.8} markerEnd="url(#atl-arrow)" markerStart="url(#atl-arrow)" />
          {p.ex.map((e, n) => (
            <T key={e} x={p.x + 145} y={142 + n * 18} s={11.5}>
              {e}
            </T>
          ))}
          <rect x={p.x + 30} y={190} width={230} height={30} rx={8} fill={p.bg} />
          <T x={p.x + 145} y={209} s={11.5} c={p.c} w={650}>
            {p.st}
          </T>
        </g>
      ))}
    </Svg>
  ),
};
