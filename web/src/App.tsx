import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import {
  Bot,
  Boxes,
  Code2,
  Network,
  ShieldCheck,
  ChevronRight,
  PanelLeftClose,
  Compass,
  Activity,
  Workflow,
  GitBranch,
  Home as HomeIcon,
  BookOpen,
} from "lucide-react";
import { request, type Context, type Doc } from "./studio";
import ArmView, { type ArmMode } from "./ArmView";
import { partOfJoint } from "./robotParts";
import { AudienceContext, storeAudience, storedAudience, type Audience } from "./audience";
import "./studio.css";
import "./lab.css";
const LeaderFollower = lazy(() => import("./LeaderFollower")),
  ModelicaEditor = lazy(() => import("./ModelicaEditor")),
  DualCopilot = lazy(() => import("./DualCopilot")),
  Knowledge = lazy(() => import("./EngineeringKnowledge")),
  Journey = lazy(() => import("./Journey")),
  SimLab = lazy(() => import("./SimLab")),
  ModelPipeline = lazy(() => import("./ModelPipeline")),
  Reasoning = lazy(() => import("./Reasoning")),
  Home = lazy(() => import("./Home")),
  Atlas = lazy(() => import("./Atlas"));
// Overview.tsx and ReasoningBenchmark.tsx are kept for internal use but are not part of the product navigation.
// Indices are stable deep-link targets (open(i)); NAV_ORDER is the order shown in the rail.
// [name, icon, short subtitle, purpose shown in the top bar]
const tabs = [
  ["Robot & motion", Boxes, "Move, record, replay", "Move the leader arm, record a motion and replay it on the follower."],
  ["Model editor", Code2, "Edit, validate, accept", "Edit the Modelica model, check it with OpenModelica and accept new revisions."],
  ["AI assistant", Bot, "Ask the local copilot", "Ask the local AI (Nemotron) to explain behaviour and draft changes - with and without the knowledge graph."],
  ["Knowledge graph", Network, "Entities & provenance", "Browse the robot's facts in the knowledge graph and the trace of past engineering decisions."],
  ["Guided demo", Compass, "Seven steps, start to finish", "A guided walk through the whole engineering flow on one joint."],
  ["Joint simulation", Activity, "Tune a servo, simulate", "Change a joint's servo settings and compare real OpenModelica simulations."],
  ["Generate model", Workflow, "URDF → Modelica, checked", "Convert the robot description into a Modelica model and verify it."],
  ["Engineering reasoning", GitBranch, "Why a value is trusted", "See how each value is known (verified, derived, assumed) and catch modelling errors automatically."],
  ["Home", HomeIcon, "What this studio does", "Overview of the studio and its five-step engineering flow."],
  ["Physical AI Atlas", BookOpen, "The ideas, explained", "A map of the concepts behind the studio: robots, physics models, knowledge graphs, learning and the sim-to-real gap."],
] as const;
// The Atlas is shown in the Overview view; in the Engineering view it is opt-in (a refresher), remembered per browser.
const ATLAS = 9;
const storedAtlas = () => {
  try {
    return localStorage.getItem("kkh.atlas") === "1";
  } catch {
    return false;
  }
};
// The rail follows the engineering flow; indices stay stable for deep links and open(i).
const NAV_GROUPS: { label: string; items: number[] }[] = [
  { label: "Start", items: [8, 9, 4] },
  { label: "1 · Robot", items: [0] },
  { label: "2 · Knowledge", items: [7, 3] },
  { label: "3 · Model", items: [6, 1] },
  { label: "4 · Simulate", items: [5] },
  { label: "5 · Decide", items: [2] },
];
// The arm in the rail changes its look with the engineering step of the current page.
const MODE: Record<number, ArmMode> = { 0: "robot", 1: "model", 2: "decide", 3: "knowledge", 4: "robot", 5: "simulate", 6: "model", 7: "knowledge", 8: "robot", 9: "robot" };
// One plain-language sentence per page, shown in the Overview view.
const PLAIN: Record<number, string> = {
  8: "This studio checks robot changes on a computer model first, so nothing is tried blindly on the real machine.",
  4: "A short tour: we follow one part of the arm (the shoulder) from its specification to a tested, approved change.",
  0: "Here you move the robot arm on screen, record a movement and play it back - like a flight recorder for the arm.",
  7: "Every number about the arm comes from somewhere. This page shows where, how sure we are, and catches mistakes automatically.",
  3: "A map of everything the studio knows about the robot: its parts, how they connect, and where each fact comes from.",
  6: "The studio turns the robot's specification file into a physics model a computer can calculate with - and checks it.",
  1: "The physics model of the robot, as code. Changes are saved as versions and only approved after a successful check.",
  5: "Try a new setting for one motor and see, in a real physics simulation, whether the arm follows its target better or worse.",
  2: "Ask questions in plain language. A local AI explains; it can suggest changes, but a person always decides.",
  9: "New to robots? Each page explains one idea in plain words and shows where to see it in the studio.",
};
const STEPS: { label: string; pages: number[]; hint: string }[] = [
  { label: "Start", pages: [8, 9, 4], hint: "Home, Physical AI Atlas and guided demo" },
  { label: "Robot", pages: [0], hint: "What is the machine? Move it, record a motion." },
  { label: "Knowledge", pages: [7, 3], hint: "What do we know about it, and how sure are we?" },
  { label: "Model", pages: [6, 1], hint: "Turn the robot into a physics model and check it." },
  { label: "Simulate", pages: [5], hint: "Change a setting and simulate the effect." },
  { label: "Decide", pages: [2], hint: "Ask the AI, review and approve changes." },
];
const groupOf = (i: number) => NAV_GROUPS.find((g) => g.items.includes(i))?.label || "";
// Deep links: ?ws=home|atlas|journey|reasoning|pipeline|lab|editor|robot|copilot|knowledge (plus workspace-specific parameters).
const WS: Record<string, number> = { robot: 0, editor: 1, copilot: 2, knowledge: 3, journey: 4, lab: 5, pipeline: 6, reasoning: 7, home: 8, atlas: 9 };
const initialWs = WS[new URLSearchParams(location.search).get("ws") || ""] ?? 8;

// A stale lazy bundle after a local rebuild must not unmount other workspaces
// (which may contain an unsaved recording or source edit).
class WorkspaceBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return (
      <section className="wb-workspace" role="alert">
        <h2>This workspace could not load</h2>
        <p className="wb-notice">A local application rebuild may have replaced its files. Other workspaces remain available. Save any ongoing recording or source edits before reloading; saved records stay in local storage.</p>
        <button onClick={() => window.location.reload()}>Reload studio</button>
      </section>
    );
    return this.props.children;
  }
}
export default function App() {
  const [active, setActive] = useState(initialWs),
    [visited, setVisited] = useState(new Set([initialWs])),
    [collapsed, setCollapsed] = useState(false),
    [context, setState] = useState<Context>({
      selected: "elbow",
      robot: "aloha_wx250s",
      file: "Arms/AlohaVX300s.mo",
    }),
    [session, setSession] = useState<Doc>(),
    [ready, setReady] = useState(false),
    [audience, setAudienceState] = useState<Audience>(storedAudience);
  const setAudience = (a: Audience) => {
    setAudienceState(a);
    storeAudience(a);
  };
  const simple = audience === "simple";
  const [atlasOn, setAtlasOn] = useState(storedAtlas);
  const showAtlas = simple || atlasOn || active === ATLAS;
  const toggleAtlas = () => {
    const on = !atlasOn;
    setAtlasOn(on);
    try {
      localStorage.setItem("kkh.atlas", on ? "1" : "0");
    } catch {
      /* per-viewer convenience only */
    }
    if (on) choose(ATLAS);
    else if (active === ATLAS) choose(8);
  };
  useEffect(() => {
    let disposed = false;
    request<Doc[]>("/documents/session")
      .then(async (records) => {
        let record = records.find(
          (d) => d.name === "Engineering studio context",
        );
        if (!record)
          record = await request<Doc>("/documents/session", "POST", {
            name: "Engineering studio context",
            data: { context },
          });
        if (!disposed) {
          setSession(record);
          if (record.data.context) {
            const loaded = record.data.context;
            if (loaded.model) {
              try {
                const model = await request<Doc>("/record/" + loaded.model);
                loaded.model_revision = model.data.head;
              } catch {}
            }
            setState(loaded);
          }
          setReady(true);
        }
      })
      .catch(() => setReady(true));
    return () => {
      disposed = true;
    };
  }, []);
  const setContext = (change: Partial<Context>) =>
    setState((old) => ({ ...old, ...change }));
  useEffect(() => {
    if (!session || !ready) return;
    const timer = setTimeout(
      () =>
        request<Doc>("/record/" + session.id, "PATCH", {
          name: session.name,
          version: session.version,
          data: { context },
        })
          .then(setSession)
          .catch(() => {}),
      600,
    );
    return () => clearTimeout(timer);
  }, [context, ready]);
  const choose = (index: number) => {
    setActive(index);
    setVisited((old) => new Set([...old, index]));
  };
  return (
    <div className={"wb-app " + (collapsed ? "compact" : "")}>
      <aside className="wb-sidebar">
        <a className="wb-brand" href="/">
          HT <span>GEN7</span> <small>PHYSAI STUDIO</small>
        </a>
        <div className="wb-armcard" aria-label="The ALOHA 2 follower arm - click a part to focus on it">
          <ArmView
            focus={context.selected}
            mode={MODE[active]}
            theme="dark"
            height={150}
            onSelect={(joint) => setContext({ selected: joint, robot: "aloha_vx300s" })}
          />
          <div className="wb-armrobot" role="group" aria-label="Which arm">
            {(
              [
                ["aloha_vx300s", "Follower"],
                ["aloha_wx250s", "Leader"],
              ] as const
            ).map(([id, label]) => (
              <button key={id} className={context.robot === id ? "on" : ""} aria-pressed={context.robot === id} onClick={() => setContext({ robot: id })}>
                {label}
              </button>
            ))}
          </div>
          <div className="wb-armcap">
            <small>ALOHA 2 · follower arm · click a part</small>
            <strong>{partOfJoint(context.selected)?.name || context.selected.replaceAll("_", " ")}</strong>
            <span>{simple ? partOfJoint(context.selected)?.plain || "" : `joint ${context.selected} · ${partOfJoint(context.selected)?.expert || ""}`}</span>
          </div>
        </div>
        <nav aria-label="Studio sections">
          {NAV_GROUPS.map((g) => (
            <div key={g.label} className="wb-nav-group">
              <span className="wb-nav-label">{g.label}</span>
              {g.items.filter((index) => index !== ATLAS || showAtlas).map((index) => {
                const [label, Icon, sub] = tabs[index];
                return (
                  <button
                    key={label}
                    className={active === index ? "active" : ""}
                    aria-current={active === index ? "page" : undefined}
                    onClick={() => choose(index)}
                    title={tabs[index][3]}
                  >
                    <Icon size={18} />
                    <span>
                      <strong>{label}</strong>
                      <small>{sub}</small>
                    </span>
                    {active === index && <ChevronRight size={14} />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="wb-sidebar-bottom">
          <ShieldCheck size={18} />
          <p>
            Local by design<small>Ollama · OpenModelica · GraphDB</small>
          </p>
        </div>
        <button
          className="wb-collapse"
          aria-label="Toggle sidebar"
          onClick={() => setCollapsed(!collapsed)}
        >
          <PanelLeftClose size={17} />
          <span>Collapse workspace rail</span>
        </button>
      </aside>
      <main className="wb-main">
        <header className="wb-topbar">
          <nav className="wb-steps-bar" aria-label="Engineering steps">
            {STEPS.map((st, i) => {
              const current = st.pages.includes(active),
                done = i > 0 && STEPS.findIndex((x) => x.pages.includes(active)) > i;
              return (
                <button
                  key={st.label}
                  className={"wb-step" + (current ? " on" : "") + (done ? " done" : "") + (i === 0 ? " start" : "")}
                  aria-current={current ? "step" : undefined}
                  onClick={() => choose(st.pages[0])}
                  title={st.hint}
                >
                  {i > 0 && <span className="wb-step-n">{i}</span>}
                  <span className="wb-step-t">
                    <b>{st.label}</b>
                    {current && i > 0 && <small>{tabs[active][0]}</small>}
                  </span>
                </button>
              );
            })}
          </nav>
          <div className="wb-top-right">
            <span className="wb-audience" role="group" aria-label="Level of engineering detail" title="Choose how much engineering detail to show">
              {(
                [
                  ["simple", "Overview"],
                  ["expert", "Engineering"],
                ] as const
              ).map(([a, l]) => (
                <button key={a} className={audience === a ? "on" : ""} aria-pressed={audience === a} onClick={() => setAudience(a)}>
                  {l}
                </button>
              ))}
            </span>
            {!simple && (
              <button className={"wb-atlas-toggle" + (atlasOn ? " on" : "")} aria-pressed={atlasOn} onClick={toggleAtlas} title="Show the Physical AI Atlas in the menu - a refresher on the concepts">
                <BookOpen size={14} /> Atlas
              </button>
            )}
            <button
              className="wb-atlas-toggle"
              title="Back to the simplified studio: Convert & compare, Understand & fix"
              onClick={() => {
                try {
                  localStorage.setItem("kkh.ui", "simple");
                } catch {}
                location.href = "/?ui=simple";
              }}
            >
              Simple view
            </button>
            <span className="wb-live" /> LOCAL
          </div>
        </header>
          {simple && (
            <div className="wb-plain" role="note">
              <b>In plain words</b> {PLAIN[active]}
            </div>
          )}
          <AudienceContext.Provider value={audience}>
          {ready &&
            [...visited].map((i) => (
              <div key={i} hidden={active !== i}>
                <WorkspaceBoundary>
                <Suspense fallback={<div className="wb-loading">Loading engineering workspace…</div>}>
                {i === 0 ? (
                  <LeaderFollower context={context} setContext={setContext} open={choose} />
                ) : i === 1 ? (
                  <ModelicaEditor context={context} setContext={setContext} />
                ) : i === 2 ? (
                  <DualCopilot context={context} />
                ) : i === 3 ? (
                  <Knowledge context={context} setContext={setContext} />
                ) : i === 4 ? (
                  <Journey context={context} setContext={setContext} open={choose} />
                ) : i === 5 ? (
                  <SimLab context={context} setContext={setContext} open={choose} />
                ) : i === 6 ? (
                  <ModelPipeline context={context} setContext={setContext} open={choose} />
                ) : i === 7 ? (
                  <Reasoning context={context} setContext={setContext} open={choose} />
                ) : i === ATLAS ? (
                  <Atlas open={choose} />
                ) : (
                  <Home context={context} setContext={setContext} open={choose} />
                )}
                </Suspense>
                </WorkspaceBoundary>
              </div>
            ))}
          </AudienceContext.Provider>
        <footer className="wb-footer">
          HT GEN7 PhysAI Studio · Engineering-Grounded Physical AI{" "}
          <span>Source facts · explicit assumptions · measured simulation</span>
        </footer>
      </main>
    </div>
  );
}
