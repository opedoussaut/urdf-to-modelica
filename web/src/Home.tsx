import { useEffect, useState } from "react";
import { Boxes, Network, Workflow, Activity, Bot, ArrowRight, CheckCircle2, CircleAlert, PlayCircle } from "lucide-react";
import { request, type Context } from "./studio";
import ArmView from "./ArmView";
import { PARTS, partOfJoint, type Part } from "./robotParts";
import { useAudience } from "./audience";

/** Plain-language entry point: what the studio is for, the five-step flow, and what is real vs experimental. */
const FLOW = [
  {
    n: 1,
    icon: Boxes,
    title: "Robot",
    question: "What is the machine?",
    does: "Load the real ALOHA 2 robot description (URDF) and move the arms in 3D.",
    gets: "Joints, limits, masses — straight from the manufacturer's files.",
    open: 0,
    action: "Robot & motion",
  },
  {
    n: 2,
    icon: Network,
    title: "Knowledge",
    question: "What do we know, and how sure are we?",
    does: "Store every robot fact in a knowledge graph with its unit and source.",
    gets: "Each value labelled verified, derived or assumed; automatic error checks.",
    open: 7,
    action: "Engineering reasoning",
  },
  {
    n: 3,
    icon: Workflow,
    title: "Model",
    question: "Can we compute with it?",
    does: "Convert the robot description into an executable Modelica physics model.",
    gets: "A model checked by OpenModelica, traceable element by element.",
    open: 6,
    action: "Generate model",
  },
  {
    n: 4,
    icon: Activity,
    title: "Simulate",
    question: "What happens if we change something?",
    does: "Tune a joint's servo settings and run a real simulation.",
    gets: "Measured tracking error, torque and settling — before vs after.",
    open: 5,
    action: "Joint simulation",
  },
  {
    n: 5,
    icon: Bot,
    title: "Decide",
    question: "Should we accept the change?",
    does: "Ask the local AI to explain; propose a change; validate; approve.",
    gets: "Nothing is accepted without a passing simulation and a human click.",
    open: 2,
    action: "AI assistant",
  },
];

const GLOSSARY: [string, string][] = [
  ["URDF", "The robot's description file from the manufacturer: links, joints, limits, masses."],
  ["Knowledge graph", "A database of engineering facts with their units and sources (GraphDB, using the CORA, QUDT and PROV-O standards)."],
  ["Modelica", "A language for physics models that can be simulated, not just animated."],
  ["OpenModelica", "The open-source tool that compiles and runs those models on this computer."],
  ["Revision", "A saved version of the model. Changes become new revisions; only validated ones can be accepted."],
  ["Local AI", "A language model (NVIDIA Nemotron) running on this laptop; it explains, it never decides."],
];

export default function Home({ context, setContext, open }: { context: Context; setContext: (c: Partial<Context>) => void; open: (i: number) => void }) {
  const [ready, setReady] = useState<any>(),
    [hover, setHover] = useState<Part>();
  const simple = useAudience() === "simple";
  const shown = hover || partOfJoint(context.selected) || PARTS[1];
  useEffect(() => {
    request("/lab/readiness").then(setReady).catch(() => {});
  }, []);
  return (
    <div className="lab home">
      <section className="home-hero">
        <div className="home-hero-text">
        <span className="lab-eyebrow">HT GEN7 PHYSAI STUDIO · ENGINEERING-GROUNDED PHYSICAL AI</span>
        <h1>Test robot changes on a trustworthy engineering model — before touching the hardware.</h1>
        <p>
          The studio takes the real description of the ALOHA 2 robot, records what is known about it (and how reliably), turns it
          into an executable physics model, and lets you simulate, compare and approve changes. Everything runs locally on this
          computer.
        </p>
        <div className="lab-actions">
          <button className="lab-primary" onClick={() => open(4)}>
            <PlayCircle size={16} /> Start the guided demo (5 min)
          </button>
          <button
            className="lab-ghost"
            onClick={() => {
              // Explore = a clean live arm, not the last recording or simulation (they stay in the Robot page lists).
              setContext({ trajectory: undefined, run: undefined });
              open(0);
            }}
          >
            Explore the robot
          </button>
        </div>
        </div>
        <div className="home-arm">
          <ArmView
            focus={shown.joint}
            mode="robot"
            theme="light"
            height={330}
            onSelect={(joint) => setContext({ selected: joint, robot: "aloha_vx300s" })}
            onHover={setHover}
          />
          <div className="home-part">
            <span className="lab-eyebrow">{hover ? "THIS PART" : "IN FOCUS"} · ALOHA 2 FOLLOWER ARM</span>
            <b>{shown.name}</b>
            <span>{simple ? shown.plain : `${shown.plain} · ${shown.expert}`}</span>
          </div>
          <div className="home-parts" role="group" aria-label="Parts of the arm">
            {PARTS.map((p) => (
              <button
                key={p.joint}
                className={p.joint === shown.joint ? "on" : ""}
                onMouseEnter={() => setHover(p)}
                onMouseLeave={() => setHover(undefined)}
                onClick={() => setContext({ selected: p.joint, robot: "aloha_vx300s" })}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section aria-label="How the studio works">
        <h2 className="home-h2">How it works — five steps</h2>
        <ol className="home-flow">
          {FLOW.map((f, i) => (
            <li key={f.n}>
              <button className="home-step" onClick={() => open(f.open)}>
                <span className="home-step-top">
                  <span className="lab-chain-n">{f.n}</span>
                  <f.icon size={18} />
                  <b>{f.title}</b>
                </span>
                <em>{f.question}</em>
                <span className="home-does">{f.does}</span>
                <span className="home-gets">→ {f.gets}</span>
                <span className="home-open">
                  {f.action} <ArrowRight size={13} />
                </span>
              </button>
              {i < FLOW.length - 1 && <ArrowRight className="home-arrow" size={18} />}
            </li>
          ))}
        </ol>
      </section>

      <div className="home-grid">
        <section className="lab-card">
          <h2>Why this matters</h2>
          <p className="home-text">
            An animation shows a robot moving. An engineering model computes <b>why</b> it moves the way it does — torques, limits,
            tracking errors — from traceable parameters. Combined with a knowledge graph, the studio knows which numbers are
            manufacturer facts (never changed) and which are assumptions (safe to tune), and it catches modelling mistakes such as
            a limit written in degrees instead of radians.
          </p>
          <h3>Words used in the studio</h3>
          <dl className="home-gloss">
            {GLOSSARY.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </section>
        <div className="home-side">
          <section className="lab-card">
            <h2>What is real · what is not yet</h2>
            <ul className="home-list ok">
              <li>Robot data from the manufacturer's files, with checksums</li>
              <li>Knowledge-graph reasoning and automatic rule checks</li>
              <li>Real OpenModelica simulations and comparisons</li>
              <li>Human approval for every model change</li>
            </ul>
            <ul className="home-list warn">
              <li>Servo settings are assumptions, not measured on the robot</li>
              <li>No validated grasping, contact or collision model</li>
              <li>No trained robot AI policy; the local AI only explains</li>
            </ul>
          </section>
          <section className="lab-card">
            <h2>System status</h2>
            <ul className="home-status">
              {(ready?.items || []).map((i: any) => (
                <li key={i.id} className={i.ok ? "ok" : "fail"} title={i.detail}>
                  {i.ok ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />} {i.label}
                </li>
              ))}
              {!ready && <li className="lab-muted">Checking…</li>}
            </ul>
            <p className="lab-footnote">
              Current focus: {context.robot === "aloha_wx250s" ? "WidowX leader" : "ViperX follower"} · joint {context.selected}
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
