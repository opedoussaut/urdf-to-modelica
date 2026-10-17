import { useState } from "react";

/**
 * Kinematic schematic of a Modelica MultiBody class, laid out automatically from the ACTUAL `connect(...)` equations
 * returned by OpenModelica (getModelInstance). Links are bodies, joints are typed glyphs on the edges between them,
 * actuated joints show their input signal. Nothing is invented: no connection, joint or parameter is drawn unless it
 * exists in the compiled class. The native annotation layout remains available in the annotation preview.
 */
type Comp = { name: string; type: string; modifiers?: Record<string, any>; comment?: string };
type Conn = { from: string; to: string };

const short = (t: string) => (t || "").split(".").at(-1) || "";
const owner = (ref: string) => ref.split(".")[0];
const port = (ref: string) => ref.split(".").slice(1).join(".");

export function schematicApplies(components: Comp[], connections: Conn[]) {
  const links = components.filter((c) => short(c.type) === "RigidLink").length;
  const joints = components.filter((c) => /Joint$/.test(short(c.type))).length;
  return links >= 2 && joints >= 1 && connections.some((c) => c.from.includes("frame_") || c.to.includes("frame_"));
}

type Node = { name: string; x: number; y: number };

export default function KinematicSchematic({
  components,
  connections,
  selected,
  onSelect,
  onOpen,
}: {
  components: Comp[];
  connections: Conn[];
  selected?: string;
  onSelect: (n: string) => void;
  onOpen: (t: string) => void;
}) {
  const [zoom, setZoom] = useState<"fit" | "full">("fit");
  const byName = new Map(components.map((c) => [c.name, c]));
  const isLink = (n: string) => short(byName.get(n)?.type || "") === "RigidLink";
  const isJoint = (n: string) => /Joint$/.test(short(byName.get(n)?.type || ""));

  // joint -> parent link (frame_a side) and child link (frame_b side), from the real connect equations
  const parent = new Map<string, string>(),
    child = new Map<string, string>(),
    inputs = new Map<string, string>();
  let root: string | undefined;
  for (const c of connections) {
    for (const [a, b] of [
      [c.from, c.to],
      [c.to, c.from],
    ]) {
      const oa = owner(a),
        ob = owner(b);
      if (isJoint(oa) && port(a) === "frame_a" && isLink(ob)) parent.set(oa, ob);
      if (isJoint(oa) && port(a) === "frame_b" && isLink(ob)) child.set(oa, ob);
      if (isJoint(oa) && port(a) === "q") inputs.set(oa, b);
      if (a === "frame_a" && isLink(ob)) root = ob;
    }
  }
  const joints = [...parent.keys()].filter((j) => child.has(j));
  const kids = new Map<string, { joint: string; link: string }[]>();
  for (const j of joints) kids.set(parent.get(j)!, [...(kids.get(parent.get(j)!) || []), { joint: j, link: child.get(j)! }]);
  const hasParent = new Set(joints.map((j) => child.get(j)!));
  root ??= components.find((c) => isLink(c.name) && !hasParent.has(c.name))?.name;
  if (!root) return <p className="wb-notice">No kinematic tree found in this class.</p>;

  // main chain = deepest path from the root; other subtrees hang below their parent link
  const depth = (l: string): number => 1 + Math.max(0, ...(kids.get(l) || []).map((k) => depth(k.link)));
  const chain: string[] = [root];
  for (let cur = root; (kids.get(cur) || []).length; ) {
    const next = [...kids.get(cur)!].sort((a, b) => depth(b.link) - depth(a.link))[0].link;
    chain.push(next);
    cur = next;
  }
  const PER_ROW = 4,
    DX = 290,
    ROW = 330,
    W = 190,
    H = 64;
  const pos = new Map<string, Node>();
  chain.forEach((l, i) => {
    const row = Math.floor(i / PER_ROW),
      col = i % PER_ROW,
      x = (row % 2 === 0 ? col : PER_ROW - 1 - col) * DX;
    pos.set(l, { name: l, x, y: row * ROW });
  });
  const rowEnd = (l: string) => {
    const i = chain.indexOf(l);
    return i >= 0 && (i % PER_ROW === PER_ROW - 1 || i === chain.length - 1) && i < chain.length - 1;
  };
  const place = (l: string) => {
    const p = pos.get(l)!;
    const side = (kids.get(l) || []).filter((k) => !pos.has(k.link));
    side.forEach((k, n) => {
      const i = chain.indexOf(l),
        row = Math.floor(i / PER_ROW),
        outward = row % 2 === 0 ? 1 : -1;
      // Branches hang one level below their parent, side by side; at a row turn they go outward so they
      // never cross the vertical turn edge.
      const x = (rowEnd(l) ? p.x + outward * DX : p.x) + n * (W + 70) * outward;
      pos.set(k.link, { name: k.link, x, y: p.y + 200 });
      place(k.link);
    });
  };
  chain.forEach(place);

  const xs = [...pos.values()].map((p) => p.x),
    ys = [...pos.values()].map((p) => p.y);
  const vb = { x: Math.min(...xs) - W / 2 - 70, y: Math.min(...ys) - 70, w: Math.max(...xs) - Math.min(...xs) + W + 140, h: Math.max(...ys) - Math.min(...ys) + 150 };

  const mass = (l: string) => {
    const m = byName.get(l)?.modifiers || {};
    return m.hasInertia === "true" && m.m ? `${(+m.m).toFixed(3)} kg` : "massless frame";
  };
  const glyph = (j: string, x: number, y: number, vertical = false, onBus = false) => {
    const t = short(byName.get(j)?.type || ""),
      m = byName.get(j)?.modifiers || {},
      sel = selected === j,
      inp = inputs.get(j),
      movable = t !== "FixedJoint";
    const axis = (m.n || "").replace(/[{}\s]/g, "").split(",").map(Number);
    const ax = axis.length === 3 ? (["x", "y", "z"][axis.findIndex((v: number) => Math.abs(v) > 0.5)] || "?") + (axis.some((v: number) => v < -0.5) ? "−" : "") : "";
    return (
      <g
        key={j}
        className={"ks-joint" + (sel ? " sel" : "")}
        role="button"
        tabIndex={0}
        aria-label={`${j} ${t}`}
        onClick={() => onSelect(j)}
        onDoubleClick={() => onOpen(byName.get(j)!.type)}
        onKeyDown={(e) => e.key === "Enter" && onSelect(j)}
      >
        <title>{`${j} · ${byName.get(j)?.type}${m.q_min ? ` · [${(+m.q_min).toFixed(3)}, ${(+m.q_max).toFixed(3)}] rad` : m.s_min ? ` · [${m.s_min}, ${m.s_max}] m` : ""}`}</title>
        {t === "RevoluteJoint" && <circle cx={x} cy={y} r={15} className={"ks-rev" + (inp ? " act" : "")} />}
        {t === "RevoluteJoint" && <path d={`M${x - 7},${y + 4} A8,8 0 1 1 ${x + 6},${y + 5}`} className="ks-rot" />}
        {t === "PrismaticJoint" && <rect x={x - 17} y={y - 11} width={34} height={22} rx={4} className={"ks-pri" + (inp ? " act" : "")} />}
        {t === "PrismaticJoint" && <path d={`M${x - 9},${y} H${x + 9} M${x - 9},${y} l4,-4 M${x - 9},${y} l4,4 M${x + 9},${y} l-4,-4 M${x + 9},${y} l-4,4`} className="ks-rot" />}
        {t === "FixedJoint" && <rect x={x - 6} y={y - 6} width={12} height={12} transform={`rotate(45 ${x} ${y})`} className="ks-fix" />}
        {vertical ? (
          <>
            <text x={x + 24} y={y - 3} className="ks-jname" style={{ textAnchor: "start" }}>
              {j.replace(/^j_/, "")}
            </text>
            {movable && (
              <text x={x + 24} y={y + 16} className={"ks-input" + (inp ? "" : " eq")} style={{ textAnchor: "start" }}>
                {inp ? `${inp} · ${ax}` : `equation-driven · ${ax}`}
              </text>
            )}
          </>
        ) : (
          <>
            <text x={x} y={onBus ? y + (movable ? 52 : 26) : y - (movable ? 25 : 15)} className="ks-jname">
              {j.replace(/^j_/, "")}
            </text>
            {movable && (
              <text x={x} y={y + (t === "PrismaticJoint" ? 30 : 35)} className={"ks-input" + (inp ? "" : " eq")}>
                {inp ? `${inp} · ${ax}` : `equation-driven · ${ax}`}
              </text>
            )}
          </>
        )}
      </g>
    );
  };

  const edges: React.ReactElement[] = [],
    glyphs: React.ReactElement[] = [];
  for (const j of joints) {
    const a = pos.get(parent.get(j)!),
      b = pos.get(child.get(j)!);
    if (!a || !b) continue;
    let d: string, gx: number, gy: number, vertical = false, onBus = false;
    if (a.y === b.y) {
      const s = Math.sign(b.x - a.x);
      d = `M${a.x + (s * W) / 2},${a.y} H${b.x - (s * W) / 2}`;
      gx = (a.x + b.x) / 2;
      gy = a.y;
    } else if (a.x === b.x) {
      d = `M${a.x},${a.y + H / 2} V${b.y - H / 2}`;
      gx = a.x;
      gy = (a.y + b.y) / 2;
      vertical = true;
    } else {
      // L-shaped branch: the joint glyph sits on the branch's own horizontal segment
      // routed through a short horizontal bus just above the child bodies
      const bus = b.y - H / 2 - 22;
      d = `M${a.x},${a.y + H / 2} V${bus} H${b.x} V${b.y - H / 2}`;
      gx = (a.x + b.x) / 2;
      gy = bus;
      onBus = true;
    }
    edges.push(<path key={"e" + j} d={d} className="ks-edge" />);
    glyphs.push(glyph(j, gx, gy, vertical, onBus));
  }
  const nodes = [...pos.values()].map((p) => {
    const sel = selected === p.name,
      massless = mass(p.name) === "massless frame";
    return (
      <g
        key={p.name}
        className={"ks-link" + (sel ? " sel" : "") + (massless ? " massless" : "")}
        role="button"
        tabIndex={0}
        aria-label={`${p.name} RigidLink`}
        onClick={() => onSelect(p.name)}
        onDoubleClick={() => onOpen(byName.get(p.name)!.type)}
        onKeyDown={(e) => e.key === "Enter" && onSelect(p.name)}
      >
        <title>{`${p.name} · ${byName.get(p.name)?.comment || "RigidLink"}`}</title>
        <rect x={p.x - W / 2} y={p.y - H / 2} width={W} height={H} rx={9} />
        <text x={p.x} y={p.y - 4} className="ks-lname">
          {p.name}
        </text>
        <text x={p.x} y={p.y + 19} className="ks-lmass">
          {mass(p.name)}
        </text>
      </g>
    );
  });
  const r = pos.get(root)!;
  return (
    <div className="ks-wrap">
      <div className="ks-tools" role="group" aria-label="Zoom">
        <button className={zoom === "fit" ? "on" : ""} aria-pressed={zoom === "fit"} onClick={() => setZoom("fit")}>
          Fit
        </button>
        <button className={zoom === "full" ? "on" : ""} aria-pressed={zoom === "full"} onClick={() => setZoom("full")}>
          100 %
        </button>
      </div>
      <div className={"ks-frame " + zoom}>
      <svg
        className="ks"
        viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
        style={zoom === "full" ? { width: vb.w * 0.8, height: vb.h * 0.8, maxHeight: "none" } : undefined}
        role="img"
        aria-label="Kinematic schematic from Modelica connections"
      >
        <g className="ks-root">
          <line x1={r.x - W / 2 - 46} y1={r.y} x2={r.x - W / 2} y2={r.y} className="ks-edge" />
          <path d={`M${r.x - W / 2 - 56},${r.y + 12} h22 M${r.x - W / 2 - 52},${r.y + 12} l-6,8 M${r.x - W / 2 - 44},${r.y + 12} l-6,8 M${r.x - W / 2 - 36},${r.y + 12} l-6,8`} className="ks-ground" />
          <text x={r.x - W / 2 - 45} y={r.y - 10} className="ks-input">
            frame_a
          </text>
        </g>
        {edges}
        {nodes}
        {glyphs}
      </svg>
      </div>
      <div className="ks-legend">
        <span>
          <i className="lg-link" /> RigidLink (URDF mass)
        </span>
        <span>
          <i className="lg-rev" /> revolute joint (actuated)
        </span>
        <span>
          <i className="lg-pri" /> prismatic joint
        </span>
        <span>
          <i className="lg-fix" /> fixed joint
        </span>
        <span>
          <b>q[i] · y</b> input signal · joint axis
        </span>
        <span>
          <b>equation-driven</b> no input: driven by an equation (e.g. URDF mimic)
        </span>
      </div>
      <p className="wb-footnote">
        Auto-laid out from {connections.length} compiled connect equations ({joints.length} joints, {pos.size} bodies). Click to inspect ·
        double-click to open the class. Positions are a schematic layout, not the class's Placement annotations.
      </p>
    </div>
  );
}
