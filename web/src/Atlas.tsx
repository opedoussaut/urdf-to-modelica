import { useState } from "react";
import Markdown from "react-markdown";
import { ArrowLeft, ArrowRight, ExternalLink, Map as MapIcon } from "lucide-react";
import ArmView from "./ArmView";
import { PARTS, type Part } from "./robotParts";
import { CONCEPTS, REGIONS, ROUTE, conceptById, type Visual } from "./atlasContent";
import "./atlas.css";

/** Physical AI Atlas: a browsable map of the concepts behind the studio (no course, no quiz). */
export default function Atlas({ open }: { open: (i: number) => void }) {
  const [id, setId] = useState(() => conceptById(new URLSearchParams(location.search).get("topic"))?.id || ROUTE[0]);
  const c = conceptById(id)!;
  const i = ROUTE.indexOf(id);
  const go = (next: string) => {
    setId(next);
    try {
      const u = new URL(location.href);
      u.searchParams.set("ws", "atlas");
      u.searchParams.set("topic", next);
      history.replaceState(null, "", u);
    } catch {}
    document.querySelector(".atlas-article")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const region = REGIONS.find((r) => r.id === c.region)!;
  return (
    <div className="lab atlas">
      <header className="atlas-head">
        <span className="lab-eyebrow">
          <MapIcon size={13} /> PHYSICAL AI ATLAS
        </span>
        <h1>The ideas behind the studio, one map</h1>
        <p>Eleven short concepts, from what Physical AI is to why simulations and reality disagree. Start anywhere; each page links to where you can see it in the studio.</p>
      </header>

      <nav className="atlas-map" aria-label="Atlas map">
        {REGIONS.map((r, ri) => (
          <section key={r.id} className={"atlas-region" + (r.id === c.region ? " here" : "")} style={{ ["--rc" as any]: r.color }}>
            <span className="atlas-region-n">{ri + 1}</span>
            <b>{r.label}</b>
            <small>{r.blurb}</small>
            <div className="atlas-chips">
              {CONCEPTS.filter((x) => x.region === r.id).map((x) => (
                <button key={x.id} className={x.id === id ? "on" : ""} aria-current={x.id === id ? "page" : undefined} onClick={() => go(x.id)}>
                  {x.title.replace(/ — .*$/, "")}
                </button>
              ))}
            </div>
          </section>
        ))}
      </nav>

      <article className="atlas-article" style={{ ["--rc" as any]: region.color }}>
        <div className="atlas-article-main">
          <span className="atlas-tag">
            {region.label} · {i + 1} of {ROUTE.length}
          </span>
          <h2>{c.title}</h2>
          <p className="atlas-gist">{c.gist}</p>
          <div className="atlas-visual">
            <ConceptVisual v={c.visual} />
          </div>
          <div className="atlas-body">
            <Markdown>{c.body}</Markdown>
          </div>
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
              {i > 0 ? conceptById(ROUTE[i - 1])!.title : "—"}
            </span>
          </button>
          <button disabled={i === ROUTE.length - 1} onClick={() => go(ROUTE[i + 1])} className="next">
            <span>
              <small>Next</small>
              {i < ROUTE.length - 1 ? conceptById(ROUTE[i + 1])!.title : "—"}
            </span>
            <ArrowRight size={15} />
          </button>
        </footer>
      </article>
    </div>
  );
}

/* ---------- visuals: the real arm where it helps, small diagrams elsewhere (illustrations, no data) ---------- */

function ConceptVisual({ v }: { v: Visual }) {
  switch (v) {
    case "arm-explore":
      return <ArmExplore />;
    case "arm-swing":
      return (
        <figure className="atlas-fig">
          <ArmView focus="elbow" mode="simulate" theme="light" height={260} autoRotate={false} />
          <figcaption>The elbow swings ±0.32 rad around the ALOHA start pose; every frame is computed by forward kinematics from the URDF.</figcaption>
        </figure>
      );
    default:
      return <figure className="atlas-fig">{DIAGRAMS[v]}</figure>;
  }
}

function ArmExplore() {
  const [hover, setHover] = useState<Part>(),
    [focus, setFocus] = useState("shoulder");
  const shown = hover || PARTS.find((p) => p.joint === focus)!;
  return (
    <figure className="atlas-fig">
      <ArmView focus={shown.joint} mode="robot" theme="light" height={260} onSelect={setFocus} onHover={setHover} />
      <div className="atlas-parts">
        {PARTS.map((p) => (
          <button key={p.joint} className={p.joint === shown.joint ? "on" : ""} onMouseEnter={() => setHover(p)} onMouseLeave={() => setHover(undefined)} onClick={() => setFocus(p.joint)}>
            {p.name}
          </button>
        ))}
      </div>
      <figcaption>
        <b>{shown.name}</b> — {shown.plain}
      </figcaption>
    </figure>
  );
}

const ink = "#0f1d33",
  muted = "#64748b",
  line = "#c9d3e0",
  blue = "#1d4ed8";
const Box = ({ x, y, w, h, t, s, fill = "#fff", stroke = line, color = ink }: { x: number; y: number; w: number; h: number; t: string; s?: string; fill?: string; stroke?: string; color?: string }) => (
  <g>
    <rect x={x} y={y} width={w} height={h} rx={10} fill={fill} stroke={stroke} strokeWidth={1.4} />
    <text x={x + w / 2} y={y + h / 2 + (s ? -4 : 5)} textAnchor="middle" fontSize={14} fontWeight={650} fill={color}>
      {t}
    </text>
    {s && (
      <text x={x + w / 2} y={y + h / 2 + 14} textAnchor="middle" fontSize={11.5} fill={muted}>
        {s}
      </text>
    )}
  </g>
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

const DIAGRAMS: Partial<Record<Visual, React.ReactNode>> = {
  "sense-act": (
    <Svg label="Sense, decide, act loop" h={210}>
      <Box x={30} y={70} w={150} h={64} t="Sense" s="cameras · encoders" />
      <Box x={245} y={70} w={150} h={64} t="Decide" s="controller · policy" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Box x={460} y={70} w={150} h={64} t="Act" s="motors · gripper" />
      <Arrow d="M180 102 H240" />
      <Arrow d="M395 102 H455" />
      <Arrow d="M535 134 C535 190, 105 190, 105 140" />
      <text x={320} y={196} textAnchor="middle" fontSize={12} fill={muted}>
        the world changes — and the loop runs again, many times per second
      </text>
      <text x={320} y={40} textAnchor="middle" fontSize={12.5} fill={muted}>
        physics everywhere: inertia, gravity, friction, limits
      </text>
    </Svg>
  ),
  "servo-loop": (
    <Svg label="Servo feedback loop" h={220}>
      <Box x={20} y={70} w={110} h={58} t="Target" s="angle wanted" />
      <circle cx={175} cy={99} r={16} fill="#fff" stroke={line} strokeWidth={1.4} />
      <text x={175} y={104} textAnchor="middle" fontSize={15} fill={ink}>
        −
      </text>
      <Box x={225} y={66} w={130} h={66} t="Controller" s="kp · error, kd · speed" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Box x={395} y={66} w={100} h={66} t="Motor" s="torque (limited)" />
      <Box x={530} y={66} w={95} h={66} t="Joint" s="inertia, gravity" />
      <Arrow d="M130 99 H157" />
      <Arrow d="M191 99 H221" />
      <Arrow d="M355 99 H391" />
      <Arrow d="M495 99 H526" />
      <Arrow d="M577 132 V180 H175 V118" />
      <text x={380} y={198} textAnchor="middle" fontSize={12} fill={muted}>
        sensor: actual angle, fed back
      </text>
      <text x={203} y={88} textAnchor="middle" fontSize={11} fill={muted}>
        error
      </text>
    </Svg>
  ),
  twin: (
    <Svg label="Animation versus physics model" h={230}>
      <text x={160} y={30} textAnchor="middle" fontSize={13} fontWeight={650} fill={muted}>
        ANIMATION
      </text>
      <text x={480} y={30} textAnchor="middle" fontSize={13} fontWeight={650} fill={blue}>
        PHYSICS MODEL
      </text>
      <Box x={60} y={50} w={200} h={52} t="Positions over time" s="given by someone" />
      <Arrow d="M160 102 V130" />
      <Box x={60} y={134} w={200} h={52} t="Moving picture" s="no 'why', no 'what if'" />
      <Box x={370} y={44} w={220} h={46} t="Masses · axes · motors" s="+ a setting to try" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Arrow d="M480 90 V112" />
      <Box x={370} y={116} w={220} h={40} t="Equations of motion, solved" />
      <Arrow d="M480 156 V172" />
      <Box x={370} y={176} w={220} h={44} t="Angles · torques · errors" s="change one input, run again" />
      <line x1={320} y1={44} x2={320} y2={214} stroke={line} strokeDasharray="4 5" />
    </Svg>
  ),
  "modelica-1d": (
    <Svg label="A one-dimensional joint model as connected components" h={250}>
      <Box x={14} y={60} w={108} h={58} t="Servo" s="PD · limit · lag" fill="#e8efff" stroke="#bfd0fb" color={blue} />
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
      <text x={198} y={166} textAnchor="middle" fontSize={11.5} fill={muted}>
        measured angle and speed fed back
      </text>
      <text x={320} y={36} textAnchor="middle" fontSize={12.5} fill={muted}>
        components connected like real parts — the tool derives and solves the equations
      </text>
      <rect x={120} y={190} width={400} height={42} rx={10} fill="#f8fafc" stroke={line} />
      <text x={320} y={216} textAnchor="middle" fontSize={14} fill={ink} fontFamily="Cambria, Georgia, serif" fontStyle="italic">
        J·q̈ = τ_motor − d·q̇ − A·sin(q+φ) − τ_friction
      </text>
    </Svg>
  ),
  provenance: (
    <Svg label="Provenance labels" h={200}>
      {[
        ["VERIFIED", "from a pinned source file", "#0f7a4f", "#e3f4ec"],
        ["DERIVED", "computed by a stated method", "#0369a1", "#e0f2fe"],
        ["ASSUMED", "chosen, not measured — tunable", "#a15c07", "#fdf1dc"],
        ["SIMULATED", "output of a real OpenModelica run", "#1d4ed8", "#e8efff"],
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
  ontology: (
    <Svg label="A small knowledge graph about the elbow" h={250}>
      <Box x={250} y={20} w={140} h={44} t="elbow" fill="#eeeafc" stroke="#cfc4f5" color="#5b3fb6" />
      <Box x={20} y={150} w={160} h={44} t="Revolute joint" s="CORA" />
      <Box x={240} y={150} w={160} h={44} t="1.6 rad" s="upper limit · QUDT unit" />
      <Box x={460} y={150} w={160} h={44} t="URDF @ commit" s="PROV-O source" />
      <Arrow d="M290 64 L130 146" />
      <Arrow d="M320 64 V146" />
      <Arrow d="M350 64 L520 146" />
      <text x={170} y={100} fontSize={11.5} fill={muted}>
        is a
      </text>
      <text x={326} y={112} fontSize={11.5} fill={muted}>
        has limit
      </text>
      <text x={448} y={100} fontSize={11.5} fill={muted}>
        comes from
      </text>
      <text x={320} y={232} textAnchor="middle" fontSize={12} fill={muted}>
        rules (SHACL) check every fact: right type, right unit, value within bounds
      </text>
    </Svg>
  ),
  "leader-follower": (
    <Svg label="Leader and follower arms" h={210}>
      <Box x={30} y={60} w={170} h={70} t="Leader arm" s="WidowX 250 · moved by hand" />
      <Box x={440} y={60} w={170} h={70} t="Follower arm" s="ViperX 300 · does the work" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Arrow d="M200 95 H436" />
      <text x={318} y={84} textAnchor="middle" fontSize={12} fill={muted}>
        joint angles, many times per second
      </text>
      <Arrow d="M318 100 V150" dash />
      <Box x={220} y={152} w={196} h={46} t="Recordings" s="→ training data for a policy" />
    </Svg>
  ),
  grounding: (
    <Svg label="Answer without and with grounding" h={220}>
      <Box x={30} y={30} w={270} h={52} t="Question" s="“What is the elbow's upper limit?”" />
      <Box x={340} y={30} w={270} h={52} t="Same question" s="+ retrieved facts with sources" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Arrow d="M165 82 V112" />
      <Arrow d="M475 82 V112" />
      <Box x={30} y={116} w={270} h={56} t="Answer from memory" s="fluent — maybe invented" fill="#fdf1dc" stroke="#f3d9a8" color="#a15c07" />
      <Box x={340} y={116} w={270} h={56} t="Answer with citations" s="checkable against the source" fill="#e3f4ec" stroke="#bfe3cf" color="#0f7a4f" />
      <text x={320} y={204} textAnchor="middle" fontSize={12} fill={muted}>
        either way, a person approves any change to the model
      </text>
    </Svg>
  ),
  sim2real: (
    <Svg label="The gap between simulation and reality" h={250}>
      <Box x={30} y={30} w={210} h={60} t="Simulation" s="what the model includes" fill="#e8efff" stroke="#bfd0fb" color={blue} />
      <Box x={400} y={30} w={210} h={60} t="Real robot" s="everything, always" />
      <path d="M248 60 H392" stroke="#b42318" strokeWidth={2} strokeDasharray="6 5" />
      <text x={320} y={50} textAnchor="middle" fontSize={13} fontWeight={700} fill="#b42318">
        THE GAP
      </text>
      {["assumed servo gains", "backlash · flexibility", "contact & grasping", "calibration of the cell"].map((t, k) => (
        <g key={t} transform={`translate(${30 + (k % 2) * 300} ${118 + Math.floor(k / 2) * 46})`}>
          <rect width={280} height={36} rx={8} fill="#fdecea" stroke="#f2b8b2" />
          <text x={140} y={23} textAnchor="middle" fontSize={12.5} fill="#b42318">
            {t}
          </text>
        </g>
      ))}
      <text x={320} y={226} textAnchor="middle" fontSize={12} fill={muted}>
        closed by measuring: system identification · validation runs · labelled assumptions
      </text>
    </Svg>
  ),
};

