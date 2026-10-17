import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import {
  Bot,
  Boxes,
  Code2,
  Network,
  ShieldCheck,
  ChevronRight,
  PanelLeftClose,
} from "lucide-react";
import { request, type Context, type Doc } from "./studio";
import "./studio.css";
const LeaderFollower = lazy(() => import("./LeaderFollower")),
  ModelicaEditor = lazy(() => import("./ModelicaEditor")),
  DualCopilot = lazy(() => import("./DualCopilot")),
  Knowledge = lazy(() => import("./EngineeringKnowledge"));
// Overview.tsx and ReasoningBenchmark.tsx are kept for internal use but are not part of the product navigation.
const tabs = [
  ["Leader–Follower", Boxes, "Motion & dynamic response"],
  ["Modelica Engineering Editor", Code2, "Source & native authoring"],
  ["Dual AI Copilot", Bot, "Paired local intelligence"],
  ["Engineering Knowledge Explorer", Network, "Relationships & provenance"],
] as const;

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
  const [active, setActive] = useState(0),
    [visited, setVisited] = useState(new Set([0])),
    [collapsed, setCollapsed] = useState(false),
    [context, setState] = useState<Context>({
      selected: "elbow",
      robot: "aloha_wx250s",
      file: "Arms/AlohaVX300s.mo",
    }),
    [session, setSession] = useState<Doc>(),
    [ready, setReady] = useState(false);
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
        <div className="wb-project">
          <span className="wb-project-icon">A2</span>
          <div>
            <strong>ALOHA 2</strong>
            <small>Engineering-Grounded Physical AI</small>
          </div>
        </div>
        <span className="wb-nav-label">WORKSPACES</span>
        <nav>
          {tabs.map(([label, Icon, sub], index) => (
            <button
              key={label}
              className={active === index ? "active" : ""}
              onClick={() => choose(index)}
              title={label}
            >
              <Icon size={19} />
              <span>
                <strong>{label}</strong>
                <small>{sub}</small>
              </span>
              {active === index && <ChevronRight size={14} />}
            </button>
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
          <span>
            HT GEN7 PhysAI Studio <ChevronRight size={13} />{" "}
            <strong>{tabs[active][0]}</strong>
          </span>
          <div>
            <span className="wb-live" /> LOCAL SESSION{" "}
            <span className="wb-avatar">G7</span>
          </div>
        </header>
        <div className="wb-context">
          <span>CONTEXT</span>
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
          <span>/</span>
          <button onClick={() => choose(1)}>{context.selected}</button>
          <span>·</span>
          <button onClick={() => choose(1)}>
            revision{" "}
            {context.model_revision?.slice(0, 8) || "generated baseline"}
          </button>
          <span>·</span>
          <button onClick={() => choose(0)}>
            trajectory {context.trajectory?.slice(0, 8) || "none selected"}
          </button>
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
                ) : (
                  <Knowledge context={context} setContext={setContext} />
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
