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
} from "lucide-react";
import { request, type Context, type Doc } from "./studio";
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
  Home = lazy(() => import("./Home"));
// Overview.tsx and ReasoningBenchmark.tsx are kept for internal use but are not part of the product navigation.
// Indices are stable deep-link targets (open(i)); NAV_ORDER is the order shown in the rail.
// [name, icon, short subtitle, purpose shown in the top bar]
const tabs = [
  ["Robot & motion", Boxes, "Move, record, replay", "Move the leader arm, record a motion and replay it on the follower."],
  ["Model editor", Code2, "Edit, validate, accept", "Edit the Modelica model, check it with OpenModelica and accept new revisions."],
  ["AI assistant", Bot, "Ask the local copilot", "Ask the local AI (Nemotron) to explain behaviour and draft changes — with and without the knowledge graph."],
  ["Knowledge graph", Network, "Entities & provenance", "Browse the robot's facts in the knowledge graph and the trace of past engineering decisions."],
  ["Guided demo", Compass, "Seven steps, start to finish", "A guided walk through the whole engineering flow on one joint."],
  ["Joint simulation", Activity, "Tune a servo, simulate", "Change a joint's servo settings and compare real OpenModelica simulations."],
  ["Generate model", Workflow, "URDF → Modelica, checked", "Convert the robot description into a Modelica model and verify it."],
  ["Engineering reasoning", GitBranch, "Why a value is trusted", "See how each value is known (verified, derived, assumed) and catch modelling errors automatically."],
  ["Home", HomeIcon, "What this studio does", "Overview of the studio and its five-step engineering flow."],
] as const;
// The rail follows the engineering flow; indices stay stable for deep links and open(i).
const NAV_GROUPS: { label: string; items: number[] }[] = [
  { label: "Start", items: [8, 4] },
  { label: "1 · Robot", items: [0] },
  { label: "2 · Knowledge", items: [7, 3] },
  { label: "3 · Model", items: [6, 1] },
  { label: "4 · Simulate", items: [5] },
  { label: "5 · Decide", items: [2] },
];
const groupOf = (i: number) => NAV_GROUPS.find((g) => g.items.includes(i))?.label || "";
// Deep links: ?ws=home|journey|reasoning|pipeline|lab|editor|robot|copilot|knowledge (plus workspace-specific parameters).
const WS: Record<string, number> = { robot: 0, editor: 1, copilot: 2, knowledge: 3, journey: 4, lab: 5, pipeline: 6, reasoning: 7, home: 8 };
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
    [names, setNames] = useState<{ model?: string; status?: string; trajectory?: string }>({});
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
  // Human-readable names for the context bar (model, revision status, recording).
  useEffect(() => {
    const out: { model?: string; status?: string; trajectory?: string } = {};
    Promise.all([
      context.model ? request<Doc>("/record/" + context.model).then((m) => (out.model = m.name)).catch(() => {}) : null,
      context.model_revision
        ? request<Doc>("/record/" + context.model_revision).then((r) => (out.status = r.data.status)).catch(() => {})
        : null,
      context.trajectory ? request<Doc>("/record/" + context.trajectory).then((t) => (out.trajectory = t.name)).catch(() => {}) : null,
    ]).then(() => setNames(out));
  }, [context.model, context.model_revision, context.trajectory]);
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
        <div className="wb-project">
          <span className="wb-project-icon">A2</span>
          <div>
            <strong>ALOHA 2</strong>
            <small>Engineering-Grounded Physical AI</small>
          </div>
        </div>
        <nav aria-label="Studio sections">
          {NAV_GROUPS.map((g) => (
            <div key={g.label} className="wb-nav-group">
              <span className="wb-nav-label">{g.label}</span>
              {g.items.map((index) => {
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
          <span className="wb-crumbs">
            <span>
              {groupOf(active) && (
                <>
                  {groupOf(active)} <ChevronRight size={13} />{" "}
                </>
              )}
              <strong>{tabs[active][0]}</strong>
            </span>
            <small>{tabs[active][3]}</small>
          </span>
          <div>
            <span className="wb-live" /> LOCAL SESSION{" "}
            <span className="wb-avatar">G7</span>
          </div>
        </header>
        <div className="wb-context" aria-label="What you are working on">
          <span>WORKING ON</span>
          <span className="wb-focus" role="group" aria-label="Engineering focus robot">
            {(
              [
                ["aloha_vx300s", "ViperX follower"],
                ["aloha_wx250s", "WidowX leader"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                className={
                  (context.robot === id ? "active " : "") +
                  (id === "aloha_vx300s" ? "follower" : "leader")
                }
                aria-pressed={context.robot === id}
                onClick={() => setContext({ robot: id })}
              >
                {label}
              </button>
            ))}
          </span>
          <span className="wb-ctx-item joint">
            Joint <button onClick={() => choose(7)}>{context.selected.replaceAll("_", " ")}</button>
          </span>
          <span className="wb-ctx-item">
            Model{" "}
            <button onClick={() => choose(1)}>
              {context.model
                ? `${names.model || "editable model"} · revision ${context.model_revision?.slice(0, 8) || "—"}${names.status ? ` (${names.status})` : ""}`
                : "generated baseline (read-only)"}
            </button>
          </span>
          <span className="wb-ctx-item">
            Recording <button onClick={() => choose(0)}>{context.trajectory ? names.trajectory || context.trajectory.slice(0, 8) : "none"}</button>
          </span>
        </div>
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
                ) : (
                  <Home context={context} setContext={setContext} open={choose} />
                )}
                </Suspense>
                </WorkspaceBoundary>
              </div>
            ))}
        <footer className="wb-footer">
          HT GEN7 PhysAI Studio · Engineering-Grounded Physical AI{" "}
          <span>Source facts · explicit assumptions · measured simulation</span>
        </footer>
      </main>
    </div>
  );
}
