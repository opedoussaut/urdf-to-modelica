import { useEffect, useRef, useState } from "react";
import * as monaco from "monaco-editor/editor/editor.api";
import "monaco-editor/editor/contrib/find/browser/findController";
import "monaco-editor/editor/contrib/folding/browser/folding";
import "monaco-editor/editor/contrib/bracketMatching/browser/bracketMatching";
import "monaco-editor/editor/contrib/gotoError/browser/gotoError";
import "monaco-editor/editor/contrib/gotoSymbol/browser/goToCommands";
import "monaco-editor/editor/contrib/hover/browser/hoverContribution";
import "monaco-editor/editor/contrib/contextmenu/browser/contextmenu";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import cytoscape from "cytoscape";
import ModelicaDiagram from "./ModelicaDiagram";
import SemanticTrace from "./SemanticTrace";
import {
  ExternalLink,
  Save,
  Check,
  Play,
  RefreshCw,
  GitCompare,
  FileCode2,
} from "lucide-react";
import { request, waitJob, message, type Doc, type Context } from "./studio";
(globalThis as any).MonacoEnvironment = { getWorker: () => new EditorWorker() };
monaco.languages.register({ id: "modelica" });
monaco.languages.setMonarchTokensProvider("modelica", {
  keywords: [
    "within",
    "model",
    "block",
    "package",
    "end",
    "equation",
    "algorithm",
    "parameter",
    "constant",
    "input",
    "output",
    "connect",
    "extends",
    "import",
    "annotation",
    "if",
    "then",
    "else",
    "for",
    "loop",
    "partial",
    "encapsulated",
    "initial",
    "der",
    "true",
    "false",
  ],
  tokenizer: {
    root: [
      [/\/\/.*$/, "comment"],
      [/\/\*/, "comment", "@comment"],
      [/"([^"\\]|\\.)*"/, "string"],
      [/\b\d+(\.\d+)?([eE][+-]?\d+)?\b/, "number"],
      [
        /[a-zA-Z_]\w*/,
        { cases: { "@keywords": "keyword", "@default": "identifier" } },
      ],
    ],
    comment: [
      [/[^*]+/, "comment"],
      [/\*\//, "comment", "@pop"],
      [/\*/, "comment"],
    ],
  },
});
type Props = { context: Context; setContext: (c: Partial<Context>) => void };
export default function ModelicaEditor({ context, setContext }: Props) {
  const [workspace, setWorkspace] = useState<Doc>(),
    [files, setFiles] = useState<any[]>([]),
    [source, setSource] = useState<any>(),
    [text, setText] = useState(""),
    [filter, setFilter] = useState(""),
    [selected, setSelected] = useState<any>(),
    [tab, setTab] = useState(() => new URLSearchParams(location.search).get("view") || "source"),
    [diff, setDiff] = useState(false),
    [changes, setChanges] = useState<any>(),
    [revisions, setRevisions] = useState<Doc[]>([]),
    [diagnostics, setDiagnostics] = useState<any>(),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(""),
    [className, setClassName] = useState("ALOHA2.Experiments.RightArmReach"),
    [stopTime, setStopTime] = useState(9);
  const [modelItems,setModelItems]=useState<Doc[]>([]);
  const host = useRef<HTMLDivElement>(null),
    editor = useRef<monaco.editor.IStandaloneCodeEditor | null>(null),
    diffEditor = useRef<monaco.editor.IStandaloneDiffEditor | null>(null),
    graphHost = useRef<HTMLDivElement>(null),
    selection = useRef<(name: string) => void>(() => {});
  const dirty = !!source && text !== source.source;
  const load = async (id: string, path = context.file) => {
    const [w, f, s, r] = await Promise.all([
      request<Doc>("/record/" + id),
      request<any[]>("/model/" + id + "/files"),
      request("/model/" + id + "/source?path=" + encodeURIComponent(path)),
      request<Doc[]>("/documents/revision"),
    ]);
    setWorkspace(w);
    setFiles(f);
    setSource(s);
    setText(s.source);
    setRevisions(r.filter((v) => v.data.workspace === id));
    setContext({ model: id, model_revision: w.data.head, file: path });
    setChanges(undefined);
    request<Doc[]>("/documents/model").then(setModelItems).catch(()=>{});
  };
  useEffect(() => {
    let disposed = false;
    const open = async () => {
      try {
        let id = context.model;
        if (!id) {
          const existing = await request<Doc[]>("/documents/model");
          id = existing[0]?.id;
          if (!id) {
            const w = await request<Doc>("/documents/model", "POST", {
              name: "ALOHA engineering working copy",
            });
            id = w.id;
          }
        }
        if (!disposed) await load(id);
      } catch (e) {
        setError(message(e));
      }
    };
    open();
    return () => {
      disposed = true;
    };
  }, []);
  useEffect(() => {
    if (!host.current || !source || tab !== "source") return;
    const base = monaco.editor.createModel(source.baseline_source, "modelica"),
      modified = monaco.editor.createModel(text, "modelica");
    if (diff) {
      const ed = monaco.editor.createDiffEditor(host.current, {
        theme: "vs-dark",
        automaticLayout: true,
        readOnly: false,
        originalEditable: false,
        minimap: { enabled: false },
      });
      ed.setModel({ original: base, modified });
      diffEditor.current = ed;
    } else {
      const ed = monaco.editor.create(host.current, {
        model: modified,
        theme: "vs-dark",
        automaticLayout: true,
        fontSize: 13,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        wordWrap: "off",
        glyphMargin: true,
      });
      editor.current = ed;
    }
    const listener = modified.onDidChangeContent(() =>
      setText(modified.getValue()),
    );
    return () => {
      listener.dispose();
      editor.current?.dispose();
      diffEditor.current?.dispose();
      editor.current = null;
      diffEditor.current = null;
      base.dispose();
      modified.dispose();
    };
  }, [source, tab, diff]);
  useEffect(() => {
    const prevent = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", prevent);
    return () => window.removeEventListener("beforeunload", prevent);
  }, [dirty]);
  const [entity, setEntity] = useState<any>();
  // Shared engineering entity -> exact Modelica component via the generator's URDF<->Modelica mapping.
  useEffect(() => {
    if (!workspace || !context.selected) return;
    request(
      "/entity?robot=" +
        encodeURIComponent(context.robot || "aloha_vx300s") +
        "&joint=" +
        encodeURIComponent(context.selected),
    )
      .then(async (e: any) => {
        setEntity(e);
        const inServo = context.file === e.servo?.file;
        if (!inServo && context.file !== e.modelica.file && !dirty)
          await load(workspace.id, e.modelica.file);
      })
      .catch(() => setEntity(undefined));
  }, [context.selected, context.robot, workspace?.id]);
  useEffect(() => {
    if (!entity || !source) return;
    const name =
      context.file === entity.servo?.file
        ? entity.servo.component
        : context.file === entity.modelica.file
          ? entity.modelica.component
          : undefined;
    const match = source.components.find((c: any) => c.name === name);
    if (match) setSelected(match);
  }, [entity, source]);
  selection.current = (name: string) => {
    const component = source?.components.find((c: any) => c.name === name);
    setSelected(component);
    // Component -> engineering entity (reverse mapping); unmapped components keep the shared selection.
    request(
      "/entity?file=" +
        encodeURIComponent(context.file) +
        "&component=" +
        encodeURIComponent(name),
    )
      .then((e: any) => setContext({ selected: e.joint, robot: e.robot, file: context.file }))
      .catch(() => {});
    if (component && editor.current) {
      editor.current.revealLineInCenter(component.line);
      editor.current.setPosition({ lineNumber: component.line, column: 1 });
      editor.current.focus();
    }
  };
  useEffect(() => {
    if (tab !== "structure" || !graphHost.current || !source) return;
    const components = source.components.filter(
      (c: any) =>
        !c.prefix.includes("parameter") && !c.prefix.includes("constant"),
    );
    const names = new Set(components.map((c: any) => c.name));
    const positioned = components.some((c: any) => c.position);
    const elements: any[] = [
      ...components.map((c: any, index: number) => ({
        data: { id: c.name, label: c.name, type: c.type },
        position: c.position
          ? { x: c.position[0] * 4, y: -c.position[1] * 1.2 }
          : { x: -450 + index * 110, y: -220 },
      })),
      ...source.connections
        .filter(
          (c: string[]) =>
            names.has(c[0].split(".")[0]) && names.has(c[1].split(".")[0]),
        )
        .map((c: string[], i: number) => ({
          data: {
            id: "edge" + i,
            source: c[0].split(".")[0],
            target: c[1].split(".")[0],
            label: c.join(" ↔ "),
          },
        })),
    ];
    const graph = cytoscape({
      container: graphHost.current,
      elements,
      layout: { name: positioned ? "preset" : "breadthfirst" },
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            color: "#e0eaf5",
            "font-size": 10,
            shape: "roundrectangle",
            width: 95,
            height: 32,
            "background-color": "#244360",
            "text-valign": "center",
          },
        },
        {
          selector: "edge",
          style: {
            "line-color": "#4a7b94",
            width: 1.5,
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#4a7b94",
          },
        },
        {
          selector: ":selected",
          style: {
            "background-color": "#0D9488",
            "border-color": "#8af5dd",
            "border-width": 2,
          },
        },
      ],
    });
    graph.on("tap", "node", (e) => selection.current(e.target.id()));
    return () => graph.destroy();
  }, [source, tab]);
  const save = async (proposal = false) => {
    if (!workspace || !source) return;
    try {
      await request("/model/" + workspace.id + "/source", "PUT", {
        path: context.file,
        source: text,
        expected_hash: source.hash,
        proposal,
      });
      await load(workspace.id);
      setNotice(
        "Saved as a new working revision. Generated baseline unchanged.",
      );
    } catch (e) {
      setError(message(e));
    }
  };
  const action = async (type: string) => {
    if (!workspace) return;
    if (dirty) {
      setError("Save or revert unsaved source before this action.");
      return;
    }
    setError("");
    setBusy(type);
    try {
      const result = await request(
        "/model/" + workspace.id + "/action",
        "POST",
        {
          action: type,
          path: context.file,
          class_name: className,
          stop_time: stopTime,
        },
      );
      if (type === "open")
        setNotice(
          `Editable working package opened in native OMEdit. ${result.selection_hint || "Select the class in Libraries."} Save there, then Refresh Changes here.`,
        );
      else if(type === "engineering_variant") {
        await load(result.id,"Engineering/System.mo");
        setTab("diagram");
        setClassName("ALOHA2.Engineering.System");
        setStopTime(3.5);
        setNotice("Created an unaccepted engineering variant. Previous model, accepted revision and frozen baseline are preserved.");
      }
      else if (type === "check" || type === "simulate") {
        const checked = await waitJob(result);
        setDiagnostics(checked);
        setNotice(
          checked.valid
            ? "OpenModelica validation passed. Revision is eligible for explicit acceptance."
            : "OpenModelica reported errors; accepted revision unchanged.",
        );
        await load(workspace.id);
        const model =
          editor.current?.getModel() ||
          diffEditor.current?.getModel()?.modified;
        if (model) {
          const errors = [
            ...(checked.load.errors || []),
            ...(checked.check.errors || []),
          ].filter((e: any) => e.line);
          monaco.editor.setModelMarkers(
            model,
            "omc",
            errors.map((e: any) => ({
              severity:
                e.kind === "Error"
                  ? monaco.MarkerSeverity.Error
                  : monaco.MarkerSeverity.Warning,
              startLineNumber: +e.line,
              startColumn: +e.col || 1,
              endLineNumber: +e.line,
              endColumn: (+e.col || 1) + 1,
              message: e.msg,
            })),
          );
        }
      }
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  };
  const refresh = async () => {
    if (dirty) {
      setError(
        "Unsaved browser text is preserved. Save or revert it before reviewing native changes.",
      );
      return;
    }
    try {
      setChanges(await request("/model/" + workspace!.id + "/changes"));
      setNotice("External files inspected against the last imported revision.");
    } catch (e) {
      setError(message(e));
    }
  };
  const decide = async (action: string, revision = "") => {
    try {
      await request("/model/" + workspace!.id + "/action", "POST", {
        action,
        revision,
        hashes:
          changes?.hashes ||
          (await request("/model/" + workspace!.id + "/changes")).hashes,
      });
      await load(workspace!.id);
      setNotice(
        action === "accept"
          ? "Validated revision explicitly accepted."
          : action === "restore"
            ? "Previous revision restored into a new working revision."
            : "Native changes " +
              (action === "import"
                ? "imported as a new revision."
                : "rejected; prior working source restored."),
      );
    } catch (e) {
      setError(message(e));
    }
  };
  const setParameter = (key: string, value: string) => {
    if (!selected || !source) return;
    const escape = (v: string) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const declarationMatch = new RegExp(
      "^\\s*" +
        escape(selected.type) +
        "\\s+" +
        escape(selected.name) +
        "\\s*\\(",
      "m",
    ).exec(text);
    if (!declarationMatch) {
      setError("Edit this parameter in source.");
      return;
    }
    const start = declarationMatch.index;
    let end = start,
      depth = 0,
      quoted = false;
    for (; end < text.length; end++) {
      const c = text[end];
      if (c === '"' && text[end - 1] !== "\\") quoted = !quoted;
      if (quoted) continue;
      if ("([{".includes(c)) depth++;
      if (")]}".includes(c)) depth--;
      if (c === ";" && depth === 0) {
        end++;
        break;
      }
    }
    const declaration = text.slice(start, end);
    const binding = new RegExp("\\b" + escape(key) + "\\s*=\\s*").exec(
      declaration,
    );
    if (!binding) {
      setError("Edit this expression in source.");
      return;
    }
    const valueStart = binding.index + binding[0].length;
    let valueEnd = valueStart,
      nesting = 0,
      inString = false;
    for (; valueEnd < declaration.length; valueEnd++) {
      const c = declaration[valueEnd];
      if (c === '"' && declaration[valueEnd - 1] !== "\\") inString = !inString;
      if (inString) continue;
      if ("([{".includes(c)) nesting++;
      if (")]}".includes(c)) {
        if (nesting === 0) break;
        nesting--;
      }
      if (c === "," && nesting === 0) break;
    }
    const next =
      text.slice(0, start) +
      declaration.slice(0, valueStart) +
      value +
      declaration.slice(valueEnd) +
      text.slice(end);
    setText(next);
    editor.current?.setValue(next);
    diffEditor.current?.getModel()?.modified.setValue(next);
  };
  return (
    <div className="wb-workspace">
      <div className="wb-title">
        <div>
          <span className="wb-eyebrow">STEP 3 · MODEL</span>
          <h1>Model editor</h1>
          <p>
            Versioned source, physical structure and native OMEdit round trips.
          </p>
        </div>
        <button
          className="wb-primary"
          disabled={!workspace || !!busy}
          onClick={() => action("open")}
        >
          <ExternalLink size={15} />
          Open in OMEdit
        </button>
      </div>
      <div className="wb-toolbar wb-card">
        <span className="wb-badge">BASELINE PROTECTED</span>
        <select aria-label="Engineering model workspace" value={workspace?.id||""} onChange={e=>{
          if(dirty){setError("Save or revert unsaved source before selecting another model.");return;}
          load(e.target.value,context.file).catch(err=>setError(message(err)));
        }}><option value="" disabled>Select model…</option>{modelItems.map(m=><option key={m.id} value={m.id}>{m.name} · {m.id.slice(0,8)}</option>)}</select>
        <button disabled={!workspace||!!busy||dirty} onClick={()=>action("engineering_variant")}>Create engineering variant</button>
        <span className="wb-mono">
          Working {workspace?.data.head?.slice(0, 8) || "loading"}{" "}
          {dirty ? "· UNSAVED" : ""}
        </span>
        <button onClick={() => save()} disabled={!dirty}>
          <Save size={14} />
          Save revision
        </button>
        <button disabled={!dirty} onClick={() => save(true)}>
          Save as AI proposal
        </button>
        <button
          disabled={!dirty}
          onClick={() => {
            if (confirm("Discard unsaved browser changes?")) {
              setText(source.source);
              editor.current?.setValue(source.source);
              diffEditor.current?.getModel()?.modified.setValue(source.source);
            }
          }}
        >
          Revert unsaved
        </button>
        <button onClick={refresh} disabled={!workspace}>
          <RefreshCw size={14} />
          Refresh Changes
        </button>
      </div>
      {error && (
        <div className="wb-error" role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div className="wb-notice" role="status">
          {notice}
        </div>
      )}
      <div className="wb-editor-grid">
        <aside className="wb-card wb-filetree">
          <div className="wb-panel-heading">
            <h2>Class browser</h2>
            <FileCode2 size={16} />
          </div>
          <input
            aria-label="Search classes and components"
            placeholder="Search classes or components…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          {files
            .filter((f) => f.path.toLowerCase().includes(filter.toLowerCase()))
            .map((f) => (
              <button
                className={context.file === f.path ? "active" : ""}
                key={f.path}
                onClick={() => {
                  if (
                    dirty &&
                    !confirm(
                      "Discard unsaved browser changes and open another class?",
                    )
                  )
                    return;
                  load(workspace!.id, f.path).catch((e) =>
                    setError(message(e)),
                  );
                }}
              >
                {f.path}
              </button>
            ))}
          <h3>Components</h3>
          {source?.components
            .filter((c: any) =>
              c.name.toLowerCase().includes(filter.toLowerCase()),
            )
            .map((c: any) => (
              <button
                key={c.name}
                className={selected?.name === c.name ? "active" : ""}
                onClick={() => selection.current(c.name)}
                title={c.type}
              >
                {c.name}
                <small>{c.type.split(".").at(-1)}</small>
              </button>
            ))}
        </aside>
        <section className="wb-card wb-editor-main">
          <div className="wb-toolbar">
            <div className="wb-segment">
              {["source", "diagram", "structure"].map((t) => (
                <button
                  aria-pressed={tab === t}
                  key={t}
                  onClick={() => setTab(t)}
                >
                  {t === "source" ? "Modelica source" : t === "diagram" ? "Modelica diagram" : "Structural graph"}
                </button>
              ))}
            </div>
            <button
              aria-pressed={diff}
              disabled={tab !== "source"}
              onClick={() => setDiff(!diff)}
            >
              <GitCompare size={14} />
              Source diff
            </button>
            <select
              aria-label="Compare model revision"
              defaultValue=""
              onChange={async (e) => {
                if (dirty) {
                  setError(
                    "Save or revert unsaved edits before changing comparison.",
                  );
                  return;
                }
                try {
                  const next = await request(
                    "/model/" +
                      workspace!.id +
                      "/source?path=" +
                      encodeURIComponent(context.file) +
                      (e.target.value
                        ? "&compare_revision=" + e.target.value
                        : ""),
                  );
                  setSource(next);
                  setText(next.source);
                  setDiff(true);
                  setTab("source");
                } catch (error) {
                  setError(message(error));
                }
              }}
            >
              <option value="">Compare generated baseline</option>
              {revisions.map((r) => (
                <option key={r.id} value={r.id}>
                  Compare {r.id.slice(0, 8)} · {r.data.status}
                </option>
              ))}
            </select>
            <span className="wb-mono">{context.file}</span>
          </div>
          {tab === "source" ? (
            <div className="wb-monaco" ref={host} />
          ) : tab === "diagram" && workspace && source ? (
            <ModelicaDiagram model={workspace.id} path={context.file} hash={source.hash} selected={selected?.name} dirty={dirty}
              onSelect={name=>selection.current(name)} onOpen={type=>{
                const path=type?.replace(/^ALOHA2\./,"").replaceAll(".","/")+".mo";
                if(files.some(f=>f.path===path))load(workspace.id,path).catch(e=>setError(message(e)));
              }}/>
          ) : (
            <>
              <div className="wb-diagram" ref={graphHost} />
              <p className="wb-footnote">
                Actual component declarations and connect equations.{" "}
                {source?.layout}. Click a component to inspect parameters;
                advanced graphical authoring opens in OMEdit.
              </p>
            </>
          )}
          <div className="wb-toolbar">
            <label>
              Stop time (s)
              <input
                type="number"
                aria-label="Simulation stop time in seconds"
                min=".1"
                max="120"
                step=".1"
                value={stopTime}
                onChange={(e) => setStopTime(+e.target.value)}
              />
            </label>
            <input
              aria-label="OpenModelica class to validate"
              value={className}
              onChange={(e) => setClassName(e.target.value)}
            />
            <button
              disabled={!!busy || !workspace}
              onClick={() => action("check")}
            >
              <Check size={14} />
              Check model
            </button>
            <button
              disabled={!!busy || !workspace}
              onClick={() => action("simulate")}
            >
              <Play size={14} />
              Compile & simulate
            </button>
          </div>
          {busy && (
            <div className="wb-notice">
              {busy === "open"
                ? "Opening native editor…"
                : "OpenModelica " + busy + " in an isolated revision…"}
            </div>
          )}
          {diagnostics && (
            <details open className="wb-diagnostics">
              <summary>
                Compiler diagnostics ·{" "}
                {diagnostics.valid ? "passed" : "needs attention"}
              </summary>
              {[
                ...(diagnostics.load?.errors || []),
                ...(diagnostics.check?.errors || []),
              ].map((d: any, i: number) => (
                <button
                  key={i}
                  onClick={() => {
                    const file = files.find((f) =>
                      d.file?.replaceAll("\\", "/").endsWith("/" + f.path),
                    );
                    if (file && file.path !== context.file)
                      load(workspace!.id, file.path);
                    setTab("source");
                    setTimeout(() => {
                      editor.current?.revealLineInCenter(+d.line || 1);
                      editor.current?.setPosition({
                        lineNumber: +d.line || 1,
                        column: +d.col || 1,
                      });
                    }, 100);
                  }}
                >
                  {d.kind} · {d.file?.split(/[\\/]/).at(-1)}:{d.line} {d.msg}
                </button>
              ))}
              <pre>
                {diagnostics.check?.messages}
                {"\n"}
                {diagnostics.simulation?.messages}
              </pre>
            </details>
          )}
        </section>
        <aside className="wb-card wb-inspector">
          <div className="wb-panel-heading">
            <h2>Parameter inspector</h2>
            <span>SOURCE VALUES</span>
          </div>
          {selected ? (
            <>
              <h3>{selected.name}</h3>
              <p className="wb-mono">{selected.type}</p>
              <p>{selected.comment}</p>
              {entity && (
                <div className="wb-entity">
                  <strong>
                    {entity.robot === "aloha_vx300s" ? "Follower" : "Leader"} ·{" "}
                    {entity.joint} ({entity.type})
                  </strong>
                  <small title={entity.iri}>
                    Knowledge graph: {entity.iri.split("/aloha2/")[1]}
                  </small>
                  <small>
                    URDF {entity.urdf.file} · {entity.urdf.parent} →{" "}
                    {entity.urdf.child}
                  </small>
                  {entity.actuators && (
                    <small>
                      Actuators {entity.actuators.join(" + ")} · servo ID{" "}
                      {entity.servo_ids?.join(", ")}
                    </small>
                  )}
                  <div className="wb-toolbar">
                    {context.file !== entity.modelica.file && (
                      <button
                        onClick={() => {
                          if (dirty && !confirm("Discard unsaved edits?")) return;
                          load(workspace!.id, entity.modelica.file);
                        }}
                      >
                        Joint component {entity.modelica.component}
                      </button>
                    )}
                    {entity.servo && context.file !== entity.servo.file && (
                      <button
                        onClick={async () => {
                          if (dirty && !confirm("Discard unsaved edits?")) return;
                          try {
                            if (!files.some((f) => f.path === entity.servo.file)) {
                              // Older working copies predate the Control package: add it as its own revision.
                              await request("/model/" + workspace!.id + "/action", "POST", {
                                action: "ensure_control",
                              });
                              setNotice(
                                "Control package added to this model as a new recorded revision (generator defaults; existing files unchanged).",
                              );
                            }
                            await load(workspace!.id, entity.servo.file);
                          } catch (e) {
                            setError(message(e));
                          }
                        }}
                      >
                        Servo settings {entity.servo.component}
                      </button>
                    )}
                  </div>
                  <small>Mapping: {entity.mapping_source}</small>
                </div>
              )}
              <button
                onClick={() => {
                  const relative =
                    selected.type
                      .replace(/^ALOHA2\./, "")
                      .replaceAll(".", "/") + ".mo";
                  if (files.some((f) => f.path === relative)) {
                    if (dirty && !confirm("Discard unsaved edits?")) return;
                    load(workspace!.id, relative);
                  }
                }}
              >
                Open component class
              </button>
              <div className="wb-parameters">
                {Object.entries(selected.parameters || {}).map(
                  ([key, value]) => (
                    <label key={key}>
                      <span>
                        {key}
                        <small>
                          {parameterInfo(key)} ·{" "}
                          {selected.parameter_evidence?.[key]?.status ||
                            "working source"}
                        </small>
                      </span>
                      <input
                        aria-label={"Parameter " + key}
                        defaultValue={String(value)}
                        key={selected.name + key + source.hash + String(value)}
                        onBlur={(e) => {
                          if (e.target.value !== value)
                            setParameter(key, e.target.value);
                        }}
                      />
                    </label>
                  ),
                )}
              </div>
              <p className="wb-footnote">
                Values come from this source declaration. URDF fields are source
                facts; edits become user overrides in a new revision. Check the
                compiler before accepting. Controller settings remain
                illustrative unless identified.
              </p>
            </>
          ) : (
            <p className="wb-muted">
              Select a declared component to inspect its parameters.
            </p>
          )}
        </aside>
      </div>
      <details className="wb-card wb-pad"><summary>Selected component · ontology evidence and parameter provenance</summary><SemanticTrace context={context}/></details>
      {changes && (
        <section className="wb-card wb-pad">
          <h2>Native editor changes · {changes.changes.length} files</h2>
          {changes.changes.map((c: any) => (
            <details open key={c.path}>
              <summary>{c.path}</summary>
              <pre>{c.diff}</pre>
            </details>
          ))}
          {changes.changes.length > 0 && (
            <div className="wb-toolbar">
              <button className="wb-primary" onClick={() => decide("import")}>
                Import reviewed changes
              </button>
              <button
                onClick={() => {
                  if (
                    confirm(
                      "Reject these external edits and restore the previous imported working copy?",
                    )
                  )
                    decide("reject");
                }}
              >
                Reject changes
              </button>
            </div>
          )}
        </section>
      )}
      <section className="wb-card wb-pad">
        <div className="wb-panel-heading">
          <h2>Revision history</h2>
          <span>EXPLICIT ACCEPTANCE</span>
        </div>
        <div className="wb-revisions">
          {revisions.map((r) => (
            <div key={r.id}>
              <span className="wb-mono">{r.id.slice(0, 8)}</span>
              <strong>{r.name}</strong>
              <span className="wb-badge">
                {workspace?.data.accepted === r.id ? "accepted" : r.data.status}
              </span>
              <small>{new Date(r.created).toLocaleString()}</small>
              <button
                disabled={r.data.status !== "validated" || dirty}
                onClick={() => decide("accept", r.id)}
              >
                Accept
              </button>
              <button
                disabled={dirty || r.id === workspace?.data.head}
                onClick={() => {
                  if (confirm("Restore this revision into a new working copy?"))
                    decide("restore", r.id);
                }}
              >
                Restore
              </button>
            </div>
          ))}
        </div>
        <p className="wb-footnote">
          Baseline → working copy → optional AI proposal → compiler-validated
          revision → human-accepted revision. Restore creates another working
          revision and keeps history.
        </p>
      </section>
    </div>
  );
}
function parameterInfo(key: string) {
  if (["r", "r_CM", "r_shape", "s_min", "s_max"].includes(key))
    return "m · source / user override";
  if (["rpy", "q_min", "q_max"].includes(key))
    return "rad · source / user override";
  if (key === "m") return "kg · URDF inertial";
  if (key === "I") return "kg·m² · URDF tensor";
  if (key === "tau_max") return "N·m · URDF effort cap";
  if (key === "qd_max") return "rad/s · URDF velocity";
  if (key === "kp") return "N·m/rad · assumed servo gain, bounds 1–500";
  if (key === "kd") return "N·m·s/rad · assumed servo gain, bounds 0–80";
  if (key === "actuatorTime") return "s · assumed torque lag, bounds 0.005–0.3";
  if (key === "feedforward") return "1 · inverse-dynamics feed-forward gain, bounds 0–1";
  if (key === "n") return "unit axis · URDF joint axis";
  return "Modelica expression · compiler checked";
}
