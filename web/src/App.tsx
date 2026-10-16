import { lazy, Suspense, useEffect, useState } from "react";
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
const tabs = [
  ["Leader–Follower", Boxes, "Motion & dynamic response"],
  ["Modelica Engineering Editor", Code2, "Source & native authoring"],
  ["Dual AI Copilot", Bot, "Paired local intelligence"],
  ["Engineering Knowledge Explorer", Network, "Relationships & provenance"],
] as const;
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
          K<span>&</span>KH <small>PHYSICAL AI</small>
        </a>
        <div className="wb-project">
          <span className="wb-project-icon">A2</span>
          <div>
            <strong>ALOHA 2</strong>
            <small>Engineering Studio</small>
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
            Engineering Studio <ChevronRight size={13} />{" "}
            <strong>{tabs[active][0]}</strong>
          </span>
          <div>
            <span className="wb-live" /> LOCAL SESSION{" "}
            <span className="wb-avatar">K</span>
          </div>
        </header>
        <div className="wb-context">
          <span>CONTEXT</span>
          <strong>
            {context.robot === "aloha_wx250s"
              ? "WidowX leader"
              : "ViperX follower"}
          </strong>
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
        <Suspense
          fallback={
            <div className="wb-loading">Loading engineering workspace…</div>
          }
        >
          {ready &&
            [...visited].map((i) => (
              <div key={i} hidden={active !== i}>
                {i === 0 ? (
                  <LeaderFollower context={context} setContext={setContext} />
                ) : i === 1 ? (
                  <ModelicaEditor context={context} setContext={setContext} />
                ) : i === 2 ? (
                  <DualCopilot context={context} />
                ) : (
                  <Knowledge context={context} setContext={setContext} />
                )}
              </div>
            ))}
        </Suspense>
        <footer className="wb-footer">
          K&KH Physical AI Engineering Studio{" "}
          <span>Source facts · explicit assumptions · measured simulation</span>
        </footer>
      </main>
    </div>
  );
}
