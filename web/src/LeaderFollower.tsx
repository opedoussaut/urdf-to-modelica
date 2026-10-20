import { useEffect, useRef, useState } from "react";
import {
  Circle,
  Square,
  Play,
  Pause,
  RotateCcw,
  Save,
  Trash2,
  WandSparkles,
  Activity,
} from "lucide-react";
import RobotStage, { type SceneState } from "./RobotStage";
import PhysicsEvidence from "./PhysicsEvidence";
import {
  ArmControls,
  GuidedPanel,
  TaskResultCard,
  GUIDED_STEPS,
  initialCube,
  stepCube,
  inTarget,
  sceneFor,
  type CubeState,
} from "./CubeScenario";
import { request, waitJob, message, type Doc, type Context } from "./studio";
import {
  DEFAULT_LAYOUT,
  EXPERIMENTAL_NOTICE,
  GATES,
  LAYOUT_NAMES,
  layout as loadLayout,
  local,
  toLocal,
  toWorld,
  world,
  type Layout,
  type LocalPoint,
  type Role,
} from "./workspaceFrames";
export default function LeaderFollower({
  context,
  setContext,
  open,
}: {
  context: Context;
  setContext: (c: Partial<Context>) => void;
  open?: (workspace: number) => void;
}) {
  const [config, setConfig] = useState<any>(),
    [q, setQ] = useState<number[]>([]),
    [poses, setPoses] = useState<any>(),
    [mode, setMode] = useState("joint"),
    [camera, setCamera] = useState("perspective"),
    [notice, setNotice] = useState(""),
    [error, setError] = useState("");
  const [recording, setRecording] = useState(false),
    [draft, setDraft] = useState<any>(),
    [items, setItems] = useState<Doc[]>([]),
    [time, setTime] = useState(0),
    [playing, setPlaying] = useState(false),
    [name, setName] = useState("Leader demonstration"),
    [busy, setBusy] = useState(""),
    [simulation, setSimulation] = useState<Doc>(),
    [runItems, setRunItems] = useState<Doc[]>([]),
    [controller, setController] = useState("reference"),
    [workspace, setWorkspace] = useState<Doc>(),
    [revisions, setRevisions] = useState<Doc[]>([]),
    [referenceRevision, setReferenceRevision] = useState(""),
    [candidateRevision, setCandidateRevision] = useState("");
  const [scenario, setScenario] = useState<any>(),
    [cube, setCube] = useState<CubeState>(),
    [guided, setGuided] = useState(false),
    [step, setStep] = useState(0),
    [taskResult, setTaskResult] = useState<any>(),
    [simTask, setSimTask] = useState<any>(),
    [attemptTask, setAttemptTask] = useState<any>(),
    [retargeting, setRetargeting] = useState(""),
    [ikWorking, setIkWorking] = useState(false),
    [dragInfo, setDragInfo] = useState(""),
    // "live": operator commands drive a kinematic follower and the live cube rule;
    // "replay": a saved recording is played back (cube path from the backend, follower from OpenModelica if selected)
    [source, setSource] = useState<"live" | "replay">("live");
  const goal = useRef<number[]>([]),
    kinematicEE = useRef<number[] | null>(null),
    recordStart = useRef(0),
    traceStart = useRef<any>({}),
    gripperLog = useRef<{ t: number; command: string; opening: number }[]>([]),
    sampleCount = useRef(0),
    lifted = useRef(false),
    goalEE = useRef<number[] | null>(null);
  const current = useRef(q),
    selected = useRef(context.selected),
    ikBusy = useRef(false),
    pendingTarget = useRef<number[] | null>(null),
    // Manipulator end effector in the SCENARIO frame (display world for layout scenarios, follower base for legacy).
    taskEE = useRef<number[] | null>(null),
    // Follower joint row shown during replay of a follower-joint recording (retargeted attempt); leader parked.
    followerRow = useRef<number[] | null>(null);
  const [layoutName, setLayoutName] = useState(() => {
    try {
      const saved = localStorage.getItem("kkh.layout");
      return saved && LAYOUT_NAMES.includes(saved) ? saved : DEFAULT_LAYOUT;
    } catch {
      return DEFAULT_LAYOUT;
    }
  });
  const lay = loadLayout(layoutName);
  current.current = q;
  selected.current = context.selected;
  const refresh = () => request<Doc[]>("/documents/trajectory").then(setItems);
  const refreshRuns = () =>
    request<Doc[]>("/documents/simulation").then(setRunItems);
  useEffect(() => {
    request("/configuration")
      .then((c) => {
        setConfig(c);
        setQ(c.home);
        goal.current = [...c.home];
      })
      .catch((e) => setError(message(e)));
    refresh();
    refreshRuns();
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem("kkh.layout", layoutName);
    } catch {
      /* per-viewer convenience only */
    }
    setScenario(undefined);
    request("/scenarios/" + lay.scenario)
      .then((sc) => {
        if (sc.frame?.layout && sc.frame.layout !== lay.name)
          throw new Error(`Scenario ${sc.id} is defined in layout ${sc.frame.layout}, not ${lay.name}`);
        setScenario(sc);
        setCube(initialCube(sc));
        lifted.current = false;
      })
      .catch((e) => setError(message(e)));
  }, [layoutName]);
  useEffect(() => {
    if (context.trajectory && config)
      request<Doc>("/record/" + context.trajectory)
        .then((d) => {
          setDraft(d.data);
          setName(d.name);
          showRow(d.data, d.data.q[0]);
          setTaskResult(undefined);
          setAttemptTask(undefined);
          setSource("replay");
          if (d.data.scenario) {
            request("/trajectory/" + d.id + "/task")
              .then(setTaskResult)
              .catch((e) => setError(message(e)));
            // Shared-table scenarios: the leader demonstrates; the follower attempt is the joint-mapped replay.
            if (
              d.data.reference_space !== "follower_joints" &&
              d.data.traceability?.layout?.name &&
              d.data.traceability.layout.name !== "legacy_side_by_side"
            )
              request("/trajectory/" + d.id + "/task?manipulator=follower")
                .then(setAttemptTask)
                .catch((e) => setError(message(e)));
          }
          setTime(0);
          setPlaying(false);
        })
        .catch((e) => setError(message(e)));
  }, [context.trajectory, !!config]);
  // Recording deselected elsewhere (e.g. Home "Explore the robot"): return to a clean live view at home.
  useEffect(() => {
    if (context.trajectory || recording || !draft) return;
    setPlaying(false);
    followerRow.current = null;
    setDraft(undefined);
    setSimulation(undefined);
    setTaskResult(undefined);
    setAttemptTask(undefined);
    setSource("live");
    setTime(0);
    if (config) {
      goal.current = [...config.home];
      current.current = [...config.home];
      setQ(config.home);
    }
    if (scenario) setCube(initialCube(scenario));
    lifted.current = false;
  }, [context.trajectory]);
  // Task metrics on the OpenModelica follower response of the selected run (same declared Level-1 rule).
  useEffect(() => {
    setSimTask(undefined);
    const run = simulation?.data;
    if (!run || !run.trajectory || !draft?.scenario || run.trajectory !== context.trajectory) return;
    const name = run.results[controller] ? controller : Object.keys(run.results)[0];
    request("/trajectory/" + run.trajectory + "/task?run=" + simulation!.id + "&result=" + name)
      .then(setSimTask)
      .catch((e) => setError(message(e)));
  }, [simulation, controller, context.trajectory, draft]);
  useEffect(() => {
    if (context.run)
      request<Doc>("/record/" + context.run)
        .then(setSimulation)
        .catch((e) => setError(message(e)));
  }, [context.run]);
  // Pose updates: one request in flight, latest state wins (continuous motion never starves the 3D view or the
  // live cube rule, and no stale result overwrites a newer one).
  const [poseTick, setPoseTick] = useState(0);
  const latest = useRef<any>({});
  latest.current = { q, simulation, controller, time, source, scenario, recording, lay, followerRow: followerRow.current };
  const poseBusy = useRef(false),
    posePending = useRef(false);
  const updatePose = async () => {
    if (poseBusy.current) {
      posePending.current = true;
      return;
    }
    poseBusy.current = true;
    try {
      do {
        posePending.current = false;
        const s = latest.current;
        const p = await request("/pose", "POST", { q: s.q });
        if (s.followerRow && s.source === "replay") p.follower = await request("/follower-pose", "POST", { q: s.followerRow });
        // Cartesian leader control must use the leader base frame, not the follower frame.
        kinematicEE.current = p.leader?.ee_gripper_link?.slice(0, 3) ?? null;
        const ee = s.scenario ? scenarioEE(s.scenario, s.lay, p) : null;
        taskEE.current = ee;
        if (s.source === "live" && s.scenario && ee) {
          const t = s.recording ? (performance.now() - recordStart.current) / 1000 : 0;
          const open = opening(s.q);
          setCube((c) => {
            if (!c) return c;
            const next = stepCube(c, s.scenario, ee, open, t);
            if (next.attached && next.cube[2] > s.scenario.objects[0].size_m[2] / 2 + 0.03) lifted.current = true;
            return next;
          });
        }
        const results = s.simulation?.data.results || {};
        const result =
          s.source === "replay"
            ? results[s.controller] || results.candidate || Object.values<any>(results)[0]
            : undefined;
        if (result) {
          let i = result.time.findIndex((t: number) => t >= s.time);
          if (i < 0) i = result.time.length - 1;
          p.follower = await request("/follower-pose", "POST", { q: result.q_actual[i] });
        }
        setPoses(p);
        if (p.mapping.warnings.length) setNotice(p.mapping.warnings.join("; "));
      } while (posePending.current);
    } catch (e) {
      setError("Robot pose update failed (last valid pose kept): " + message(e));
    } finally {
      poseBusy.current = false;
    }
  };
  useEffect(() => {
    if (q.length) updatePose();
  }, [q, simulation, controller, source, source === "replay" ? time : 0, scenario, poseTick]);
  // Rate-limited command path: every operator input sets a goal; the leader moves toward it at bounded joint speed
  // (no step commands reach the recorded reference or the follower).
  useEffect(() => {
    const timer = setInterval(() => {
      const g = goal.current,
        c = current.current;
      if (!g.length || g.length !== c.length) return;
      let moved = false;
      const next = c.map((v, i) => {
        const step = i === 7 ? SLEW_GRIPPER_M_PER_S * 0.02 : SLEW_JOINT_RAD_PER_S * 0.02;
        const d = Math.max(-step, Math.min(step, g[i] - v));
        if (Math.abs(g[i] - v) > 1e-7) moved = true;
        return Math.abs(g[i] - v) <= step ? g[i] : v + d;
      });
      if (moved) {
        current.current = next;
        setQ(next);
      }
    }, 20);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!recording) return;
    const samples: number[][] = [],
      times: number[] = [];
    const start = performance.now();
    recordStart.current = start;
    sampleCount.current = 0;
    const trace = traceStart.current;
    const timer = setInterval(() => {
      times.push((performance.now() - start) / 1000);
      samples.push([...current.current]);
      sampleCount.current = samples.length;
      setTime(times.at(-1)!);
    }, 20);
    return () => {
      clearInterval(timer);
      if (times.length >= 3)
        setDraft({
          configuration_id: config.configuration_id,
          joint_ids: config.joint_ids,
          time: times.map((t) => t - times[0]),
          q: samples,
          provenance:
            "Recorded from interactive leader control, browser monotonic clock; source URDF limits enforced",
          ...(scenario ? { scenario: { id: scenario.id, version: scenario.version } } : {}),
          traceability: {
            ...trace,
            stopped_at: new Date().toISOString(),
            duration_s: times.at(-1)! - times[0],
            samples: samples.length,
            gripper_commands: [...gripperLog.current],
            command_path: `operator inputs -> goal -> rate limit (${SLEW_JOINT_RAD_PER_S} rad/s, ${SLEW_GRIPPER_M_PER_S} m/s gripper) -> recorded leader joints`,
            evidence: {
              observed: "Leader joint commands entered in the studio UI (not a physical robot measurement).",
              assumed: scenario
                ? `Level-1 visual grasp rule of scenario ${scenario.id} ${scenario.version} (capture radius, gripper thresholds, vertical drop).`
                : "none",
              simulated: "None at recording time; OpenModelica runs are linked to this recording afterwards.",
            },
          },
        });
    };
  }, [recording, config]);
  useEffect(() => {
    if (!playing || !draft) return;
    const start = performance.now() - time * 1000;
    const timer = setInterval(() => {
      const t = Math.min((performance.now() - start) / 1000, draft.time.at(-1));
      seek(t);
      if (t >= draft.time.at(-1)) setPlaying(false);
    }, 25);
    return () => clearInterval(timer);
  }, [playing, draft, simulation, controller]);
  /** Show one recorded row: leader commands drive the leader; a follower reference parks the leader at home. */
  function showRow(data: any, row: number[]) {
    const followerSpace = data?.reference_space === "follower_joints";
    followerRow.current = followerSpace ? [...row] : null;
    if (followerSpace && !config) return; // the leader home pose is required to park the leader
    const leader = followerSpace ? [...config.home] : row;
    goal.current = [...leader];
    goalEE.current = null;
    current.current = leader;
    setQ(leader);
    if (followerSpace) setPoseTick((n) => n + 1);
  }
  function seek(t: number) {
    setTime(t);
    if (!draft) return;
    let i = draft.time.findIndex((v: number) => v >= t);
    if (i < 0) i = draft.time.length - 1;
    const a = Math.max(0, i - 1),
      alpha = (t - draft.time[a]) / (draft.time[i] - draft.time[a] || 1);
    const next = draft.q[a].map((v: number, j: number) => v + (draft.q[i][j] - v) * alpha);
    showRow(draft, next);
  }
  const joints = config?.leader.joints || [];
  const limits = (index: number) => {
    const joint = joints.find((j: any) => j.name === config?.joint_ids[index]);
    return [joint?.limit?.lower ?? -Math.PI, joint?.limit?.upper ?? Math.PI];
  };
  /** Normalised leader finger opening (0 closed, 1 open) - same definition as the backend binding. */
  const opening = (row: number[]) => {
    const [lo, hi] = limits(7);
    return row.length > 7 ? (row[7] - lo) / (hi - lo || 1) : 1;
  };
  const goLive = () => {
    setPlaying(false);
    followerRow.current = null;
    if (source !== "live") {
      setSource("live");
      goal.current = [...current.current];
      goalEE.current = null;
    }
  };
  const change = (index: number, value: number) => {
    goLive();
    if (!goal.current.length) goal.current = [...current.current];
    const [lo, hi] = limits(index);
    goal.current = [...goal.current];
    if (index !== 7) goalEE.current = null;
    goal.current[index] = Math.min(hi, Math.max(lo, value));
    const joint = config?.joint_ids[index];
    setDragInfo(`${joint?.replaceAll("_", " ")} → ${goal.current[index].toFixed(index === 7 ? 4 : 3)} ${index === 7 ? "m" : "rad"}`);
  };
  const gripper = (open: boolean) => {
    const [lo, hi] = limits(7);
    change(7, open ? hi : lo);
    if (recording)
      gripperLog.current.push({
        t: (performance.now() - recordStart.current) / 1000,
        command: open ? "open" : "close",
        opening: open ? 1 : 0,
      });
  };
  const home = () => {
    goLive();
    goal.current = [...config.home];
    goalEE.current = null;
    setDragInfo("Returning to home (rate-limited)");
  };
  // The control buttons address the LEADER in its own base frame.
  // The follower IK endpoint uses a different embodiment/frame and must not be used here.
  const ikQueue = useRef<Promise<void>>(Promise.resolve());
  const leaderTarget = (target: number[], label: string) => {
    goLive();
    goalEE.current = target;
    setIkWorking(true);
    ikQueue.current = ikQueue.current.then(async () => {
      try {
        const result = await request("/ik", "POST", { q: goal.current, target });
        if (result.success) {
          goal.current = [...result.q];
          setDragInfo(`${label}: leader IK goal accepted`);
        } else {
          goalEE.current = null;
          setNotice(result.message || "Leader IK target unreachable");
        }
      } catch (e) {
        goalEE.current = null;
        setError(message(e));
      } finally {
        setIkWorking(false);
      }
    });
  };
  const jog = (axis: number, delta: number) => {
    const ee = goalEE.current ?? kinematicEE.current;
    if (!ee) {
      setNotice("Leader pose unavailable: wait for the 3D robot to load.");
      return;
    }
    const target = [...ee];
    target[axis] += delta;
    leaderTarget(target, `Leader ${["X", "Y", "Z"][axis]} ${delta > 0 ? "+" : "−"}${Math.abs(delta * 100)} cm`);
  };
  const preset = (_where: "A" | "B") => {
    // A/B positions are currently in the follower scene frame. Sending them to leader IK
    // would silently command an unrelated location. Re-enable after measured registration.
    setNotice(
      "Above A/B disabled (gate enable_ab_shortcuts = false): the layout is an experimental display transform with position IK only; orientation, collision and contact are unverified. Use the leader X/Y/Z controls.",
    );
  };
  const resetScenario = () => {
    if (recording) return setNotice("Stop the recording before resetting the scenario.");
    goLive();
    if (config) goal.current = [...config.home];
    if (scenario) setCube(initialCube(scenario));
    lifted.current = false;
    setTime(0);
    setDragInfo("Scenario reset: cube at A, arm returning home");
  };
  const toggleRecording = () => {
    setPlaying(false);
    if (!recording) {
      goLive();
      setSource("live");
      setContext({ trajectory: undefined, run: undefined });
      setSimulation(undefined);
      setDraft(undefined);
      setTaskResult(undefined);
      // The backend evaluation of a recording always starts from the scenario's initial cube pose.
      if (scenario) setCube(initialCube(scenario));
      lifted.current = false;
      gripperLog.current = [];
      traceStart.current = {
        layout: { name: lay.name, status: lay.status, bases: lay.bases, file: "config/workspace/aloha2_display_layouts.json" },
        started_at: new Date().toISOString(),
        robot_configuration: config?.configuration_id,
        leader: "aloha_wx250s",
        follower: "aloha_vx300s",
        initial_q: [...current.current],
        initial_opening: opening(current.current),
        model: context.model || null,
        model_revision: context.model_revision || workspace?.data.head || null,
        accepted_revision: workspace?.data.accepted || null,
        scenario_file: scenario?.file,
        scenario_sha256: scenario?.sha256,
      };
      if (guided) setStep(3);
    } else if (guided) setStep(4);
    setRecording(!recording);
  };
  const select = (link: string) => {
    const child = link.split("/").at(-1);
    const joint = joints.find((j: any) => j.child === child);
    // Driving the leader (joint drag / IK) changes only the joint; the engineering focus robot (usually the
    // follower under study) is changed by clicking a robot in orbit mode or by the focus switch.
    if (mode !== "orbit") setContext({ selected: joint?.name || child! });
    else
      setContext({
        selected: joint?.name || child!,
        robot: link.startsWith("leader/") ? "aloha_wx250s" : "aloha_vx300s",
      });
  };
  const target = async (t: LocalPoint<"leader">) => {
    goLive();
    goalEE.current = null;
    pendingTarget.current = [...t];
    if (ikBusy.current) return;
    ikBusy.current = true;
    try {
      while (pendingTarget.current) {
        const target = pendingTarget.current;
        pendingTarget.current = null;
        const result = await request("/ik", "POST", {
          q: current.current,
          target,
        });
        setNotice(result.message);
        if (result.success) {
          goal.current = [...result.q];
          setDragInfo("Leader end-effector IK · bounded joint goal");
        }
      }
    } catch (e) {
      setError(message(e));
    } finally {
      ikBusy.current = false;
    }
  };
  const focus = DYNAMIC_JOINTS.includes(context.selected)
    ? context.selected
    : "shoulder";
  const refreshRevisions = async () => {
    if (!context.model) return setRevisions([]);
    const [w, all] = await Promise.all([
      request<Doc>("/record/" + context.model),
      request<Doc[]>("/documents/revision"),
    ]);
    const own = all
      .filter((r) => r.data.workspace === context.model)
      .sort((a, b) => (a.created < b.created ? 1 : -1));
    setWorkspace(w);
    setRevisions(own);
    setReferenceRevision(
      (old) => old && own.some((r) => r.id === old) ? old : w.data.accepted || own.at(-1)?.id || "",
    );
    setCandidateRevision(w.data.head);
  };
  useEffect(() => {
    refreshRevisions().catch((e) => setError(message(e)));
  }, [context.model, context.model_revision]);
  const modelAction = async (body: any, label: string) => {
    if (!context.model) return;
    setBusy(label);
    setError("");
    try {
      let result: any = await request("/model/" + context.model + "/action", "POST", body);
      if (result?.kind === "job") result = await waitJob(result);
      await refreshRevisions();
      return result;
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  };
  const run = async (axes: number) => {
    if (!context.trajectory) return;
    setBusy(
      `OpenModelica · ${axes === 1 ? focus + " axis" : "six torque-driven axes"} · ${referenceRevision === candidateRevision ? "one revision" : "reference and candidate revisions"}`,
    );
    setError("");
    try {
      const record = await waitJob(
        await request(
          "/trajectory/" + context.trajectory + "/simulate?axes=" + axes,
          "POST",
          {
            model: context.model,
            reference_revision: referenceRevision || undefined,
            candidate_revision: candidateRevision || undefined,
            focus,
          },
        ),
      );
      setSimulation(record);
      setTime(0);
      setSource("replay");
      if (draft) seek(0);
      setContext({ run: record.id });
      refreshRuns();
      setNotice(record.data.conclusion);
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy("");
    }
  };
  const createAttempt = async () => {
    if (!context.trajectory) return;
    setRetargeting("Retargeting the demonstration to the follower (world-frame IK)…");
    setError("");
    try {
      const out: any = await waitJob(await request("/trajectory/" + context.trajectory + "/retarget", "POST"));
      await refresh();
      setSimulation(undefined);
      setContext({ trajectory: out.record.id, run: undefined });
      const r = out.report;
      setNotice(
        `Follower attempt created: ${(r.within_tolerance_fraction * 100).toFixed(1)} % of samples within ${r.tolerance.position_m * 1000} mm / ${r.tolerance.approach_tilt_deg}°, ` +
          `max position error ${(r.position_error_m.max * 1000).toFixed(1)} mm. Kinematic reference only: no collision or contact model. Simulate it to see the OpenModelica follower.`,
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setRetargeting("");
    }
  };
  const save = async () => {
    try {
      const record = await request<Doc>("/documents/trajectory", "POST", {
        name,
        data: draft,
      });
      setSource("replay");
      setContext({ trajectory: record.id, run: undefined });
      await refresh();
      if (guided) setStep(5);
      setNotice(
        "Recording saved locally with numerical velocities, accelerations and provenance.",
      );
    } catch (e) {
      setError(message(e));
    }
  };
  // Cube shown in 3D: live rule while operating, backend-evaluated path while replaying a saved recording.
  let shown: { cube: number[]; attached: boolean } | undefined = cube;
  if (source === "replay" && taskResult && draft?.scenario) {
    // With an OpenModelica run selected, the cube follows the simulated follower (its own time base).
    const sim = simTask && simulation ? simulation.data.results[simTask.evaluated_on.result] : undefined;
    const times: number[] = sim ? sim.time : draft.time,
      path = sim ? simTask.cube_path : taskResult.cube_path;
    let i = times.findIndex((v: number) => v >= time);
    if (i < 0) i = times.length - 1;
    const p = path[Math.min(i, path.length - 1)];
    if (p) shown = { cube: p.slice(0, 3), attached: !!p[3] };
  }
  const ee = taskEE.current;
  const near = !!(
    ee &&
    cube &&
    !cube.insideCube &&
    Math.hypot(ee[0] - cube.cube[0], ee[1] - cube.cube[1], ee[2] - cube.cube[2]) <=
      (scenario?.visual_grasp.capture_radius_m ?? 0)
  );
  const kinds = (cube?.events || []).map((e) => e.event);
  const invalidContact = !!cube?.invalidPenetrationSamples;
  const checklist = [
    { step: "perform", label: "Gripper near cube without penetrating its centre", done: (near || kinds.includes("grasp")) && !invalidContact },
    { step: "perform", label: "Gripper closed on the cube", done: kinds.includes("grasp") },
    { step: "perform", label: "Cube lifted (> 3 cm)", done: lifted.current },
    { step: "perform", label: "Cube above target area B", done: !!(cube && scenario && inTarget(scenario, cube.cube)) },
    {
      step: "perform",
      label: "Gripper opened: cube released in B",
      done: !!(cube && scenario && kinds.includes("release") && !cube.attached && inTarget(scenario, cube.cube)),
    },
    { step: "save", label: "Recording stopped", done: !recording && !!draft },
    { step: "save", label: "Recording saved with scenario and traceability", done: !!(context.trajectory && draft?.scenario) },
    { step: "save", label: "Task result computed by the backend", done: !!taskResult },
  ];
  const status = recording
    ? `● RECORDING · ${time.toFixed(1)} s · ${sampleCount.current} samples`
    : playing
      ? `▶ REPLAY · ${simulation && source === "replay" ? "follower = OpenModelica result" : "kinematic"} · ${time.toFixed(2)} s`
      : source === "replay" && draft
        ? `${draft.reference_space === "follower_joints" ? "FOLLOWER ATTEMPT · leader shown faint (it demonstrated this path in the same space)" : "SAVED RECORDING"} · ${simulation ? "OpenModelica follower selected" : "kinematic replay"} · press Play`
        : mode === "joint"
          ? `MOVE LEADER ARM${ikWorking ? " · solving IK…" : dragInfo ? " · " + dragInfo : ""}`
          : mode === "ee"
            ? "DRAG LEADER END EFFECTOR · bounded IK · rate-limited motion"
            : "LOOK AROUND (camera)";
  const help =
    mode === "joint"
      ? "Move leader arm: click a teal leader link to select its joint (highlighted), then drag left/right to rotate it. Sliders, gripper and Move-gripper buttons do the same; all commands are rate-limited. Use Look around to orbit/zoom."
      : mode === "ee"
        ? "Drag the glowing marker on the teal leader gripper in the camera plane. Bounded URDF-based IK respects joint limits; unreachable targets retain the previous goal. This controls the leader; the follower uses joint mapping."
        : "Look around: drag to orbit, scroll to zoom, click a robot to set the engineering focus. Switch to Move leader arm to control the robot.";
  const guidedActions: Record<string, React.ReactNode> = {
    prepare: (
      <button onClick={resetScenario}>
        <RotateCcw size={13} /> Reset to home with cube at A
      </button>
    ),
    practice: (
      <button className={mode === "joint" ? "" : "wb-primary"} onClick={() => setMode("joint")}>
        Activate Move leader arm
      </button>
    ),
    record: (
      <button className="wb-danger" disabled={recording} onClick={toggleRecording}>
        <Circle size={13} /> Start recording
      </button>
    ),
    perform: recording ? (
      <button className="wb-danger" onClick={toggleRecording}>
        <Square size={13} /> Stop recording
      </button>
    ) : (
      <span className="wb-muted">Not recording. Go back to step 3 to start.</span>
    ),
    save: (
      <>
        <input aria-label="Guided recording name" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="wb-primary" disabled={!draft || recording || source === "replay"} onClick={save}>
          <Save size={13} /> Save recording
        </button>
      </>
    ),
    replay: (
      <button
        disabled={!draft || recording}
        onClick={() => {
          setSource("replay");
          setPlaying(!playing);
        }}
      >
        {playing ? <Pause size={13} /> : <Play size={13} />} {playing ? "Pause replay" : "Play replay"}
      </button>
    ),
    simulate: context.model ? (
      <button className="wb-primary" disabled={!context.trajectory || !!busy} onClick={() => run(6)}>
        Simulate six axes in OpenModelica
      </button>
    ) : (
      <button onClick={() => open?.(1)}>Open the Modelica editor (creates the editable model)</button>
    ),
    diagnose: (
      <>
        <button className="wb-primary" onClick={() => open?.(2)}>
          Ask the Dual AI Copilot
        </button>
        <button onClick={() => open?.(3)}>Inspect parameters in the Knowledge Explorer</button>
        <button onClick={() => open?.(1)}>Open the Modelica editor</button>
      </>
    ),
  };
  return (
    <div className="wb-workspace">
      <div className="wb-title">
        <div>
          <span className="wb-eyebrow">STEP 1 · ROBOT</span>
          <h1>Robot &amp; motion</h1>
          <p>Shape a motion. Record the reference. Measure the follower.</p>
        </div>
        <span className="wb-badge">
          {simulation ? "TORQUE-DRIVEN RESULT" : "KINEMATIC REPLAY"}
        </span>
      </div>
      <PhysicsEvidence />
      <div className="wb-lab-grid">
        <section className="wb-card">
          {!guided && scenario && (
            <div className="wb-guided-start">
              <span>
                <strong>Cube transfer scenario</strong> · move the amber cube from A to the green area B with the
                leader arm (visual Level 1, not physics).
              </span>
              <button
                className="wb-primary"
                onClick={() => {
                  setGuided(true);
                  setStep(0);
                  setMode("joint");
                }}
              >
                Start guided cube transfer
              </button>
            </div>
          )}
          {invalidContact && source === "live" && (
            <div role="alert" className="wb-error">
              Invalid cube interaction: the end-effector reference point entered the cube. Reset the scenario and approach its surface instead. This scene does not yet simulate physical contact.
            </div>
          )}
          {guided && (
            <GuidedPanel
              step={step}
              setStep={setStep}
              onExit={() => setGuided(false)}
              onReset={resetScenario}
              checklist={checklist}
              actions={guidedActions[GUIDED_IDS[step]]}
            />
          )}
          <div className="wb-toolbar">
            <ArmControls
              mode={mode}
              setMode={setMode}
              gripper={q.length > 7 ? opening(q) : 1}
              onGripper={gripper}
              onHome={home}
              onJog={jog}
              onPreset={preset}
              busy={false}
            />
            <select
              aria-label="Camera"
              value={camera}
              onChange={(e) => setCamera(e.target.value)}
            >
              {["perspective", "front", "top", "side"].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <button onClick={resetScenario} disabled={!config || recording} title="Arm home, cube back at A">
              <RotateCcw size={14} />
              Reset scenario
            </button>
          </div>
          <RobotStage
            poses={poses}
            mode={mode}
            camera={camera}
            selected={
              (context.robot === "aloha_wx250s"
                ? "leader/"
                : "follower_right/") +
              (joints.find((j: any) => j.name === context.selected)?.child ||
                context.selected)
            }
            onSelect={select}
            onJoint={(delta) => {
              const index = config.joint_ids.indexOf(selected.current);
              if (index >= 0)
                change(
                  index,
                  (goal.current[index] ?? current.current[index]) + delta * (index === 7 ? 0.01 : 1),
                );
            }}
            onTarget={target}
            layout={lay}
            scene={shown && scenario ? sceneToWorld(sceneFor(scenario, shown.cube, shown.attached), scenario, lay) : undefined}
            status={status}
            help={help}
            ghostLeader={source === "replay" && draft?.reference_space === "follower_joints"}
          />
          <div className="wb-record-bar">
            <button className={recording ? "wb-danger" : ""} onClick={toggleRecording}>
              {recording ? <Square size={14} /> : <Circle size={14} />}{" "}
              {recording ? "Stop recording" : "Record leader"}
            </button>
            <button
              disabled={!draft || recording}
              onClick={() => {
                setSource("replay");
                setPlaying(!playing);
              }}
            >
              {playing ? <Pause size={14} /> : <Play size={14} />}{" "}
              {playing ? "Pause" : "Play"}
            </button>
            <button
              disabled={!draft || recording}
              onClick={() => {
                setPlaying(false);
                setSource("replay");
                seek(0);
              }}
            >
              <RotateCcw size={14} />
              Reset
            </button>
            <span className="wb-mono">{time.toFixed(2)} s</span>
            <input
              aria-label="Trajectory seek"
              type="range"
              min="0"
              max={draft?.time.at(-1) || 1}
              step=".01"
              value={Math.min(time, draft?.time.at(-1) || 1)}
              disabled={!draft || recording}
              onChange={(e) => {
                setPlaying(false);
                setSource("replay");
                seek(+e.target.value);
              }}
            />
          </div>
          <div className="wb-footnote">
            Teal: commanded leader · Blue:{" "}
            {simulation
              ? "selected OpenModelica follower response"
              : "joint-mapped kinematic follower"}
            . Base placement comes from the selected display layout; hardware
            registration is unknown. Amber cube / green area: Level-1 visual task
            scene (kinematic attachment, no contact physics).
          </div>
          <FrameIndicator lay={lay} scenario={scenario} layoutName={layoutName} setLayoutName={setLayoutName} disabled={recording} />
          <TaskResultCard result={taskResult} />
          <TaskResultCard result={attemptTask} compare={taskResult} />
          {taskResult?.frame && draft && draft.reference_space !== "follower_joints" && context.trajectory && (
            <div className="wb-attempt-action">
              <button className="wb-primary" disabled={!!retargeting || recording} onClick={createAttempt}>
                Create follower attempt (retarget)
              </button>
              <span>
                Maps the demonstrated gripper path through the display world and solves follower IK (position + approach
                tilt). Creates a new derived recording; the demonstration stays unchanged.
              </span>
              {retargeting && <span className="wb-muted">{retargeting}</span>}
            </div>
          )}
          {draft?.derived?.kind === "retargeted_follower_attempt" && (
            <div className="wb-attempt-action">
              <strong>Follower attempt (retargeted, kinematic)</strong>
              <span>
                Leader parked at home; the blue follower replays the retargeted reference. Within tolerance:{" "}
                {(draft.derived.report.within_tolerance_fraction * 100).toFixed(1)} % · max position error{" "}
                {(draft.derived.report.position_error_m.max * 1000).toFixed(1)} mm · max tilt error{" "}
                {draft.derived.report.approach_tilt_error_deg.max.toFixed(1)}°. Collision and contact unchecked. Use
                “Simulate six axes” below to run it on the OpenModelica follower.
              </span>
            </div>
          )}
          <TaskResultCard result={simTask} compare={taskResult} />
        </section>
        <aside className="wb-card wb-inspector">
          <div className="wb-panel-heading">
            <h2>Joint control</h2>
            <span>SI UNITS</span>
          </div>
          {config?.joint_ids.map((id: string, index: number) => {
            const joint = joints.find((j: any) => j.name === id);
            return (
              <div
                className={
                  "wb-joint " + (context.selected === id ? "selected" : "")
                }
                key={id}
              >
                <button
                  onClick={() =>
                    setContext({ selected: id })
                  }
                >
                  {id.replaceAll("_", " ")}
                  <small>{index === 7 ? "m" : "rad"}</small>
                </button>
                <input
                  aria-label={id}
                  type="range"
                  min={joint?.limit?.lower ?? -Math.PI}
                  max={joint?.limit?.upper ?? Math.PI}
                  step={index === 7 ? 0.0001 : 0.002}
                  value={q[index] ?? 0}
                  onChange={(e) => change(index, +e.target.value)}
                />
                <output>{q[index]?.toFixed(index === 7 ? 4 : 3)}</output>
              </div>
            );
          })}
          <div className="wb-callout">
            <strong>Explicit correspondence</strong>
            <p>{config?.mapping.rotational}</p>
            <p>{config?.mapping.gripper}</p>
            <p>{config?.mapping.cartesian}</p>
          </div>
        </aside>
      </div>
      {notice && (
        <div className="wb-notice" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="wb-error" role="alert">
          {error}
        </div>
      )}
      <div className="wb-lower-grid">
        <section className="wb-card wb-pad">
          <div className="wb-panel-heading">
            <h2>Motion library</h2>
            <span>LOCAL · VERSIONED</span>
          </div>
          <div className="wb-toolbar">
            <input
              aria-label="Recording name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <button disabled={!draft || recording} onClick={save}>
              <Save size={14} />
              Save recording
            </button>
          </div>
          <div className="wb-list">
            {items.map((item) => (
              <div
                key={item.id}
                className={context.trajectory === item.id ? "active" : ""}
              >
                <button
                  disabled={recording}
                  onClick={() => {
                    setContext({ trajectory: item.id, run: undefined });
                    setSimulation(undefined);
                    setDraft(item.data);
                    setName(item.name);
                    setTime(0);
                    setSource("replay");
                    showRow(item.data, item.data.q[0]);
                  }}
                >
                  <strong>{item.name}</strong>
                  <small>
                    {item.data.time.at(-1).toFixed(2)} s ·{" "}
                    {item.data.time.length} samples ·{" "}
                    {item.data.reference_space === "follower_joints"
                      ? "follower attempt (retargeted)"
                      : item.data.derived
                        ? "smoothed copy"
                        : "original"}
                  </small>
                </button>
                <a
                  href={"/api/workbench/record/" + item.id}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={"Export " + item.name}
                >
                  JSON
                </a>
                <button
                  aria-label={"Delete " + item.name}
                  onClick={async () => {
                    if (
                      !confirm(
                        "Delete this saved trajectory? Its original provenance remains in the local audit history.",
                      )
                    )
                      return;
                    try {
                      await request(
                        "/record/" +
                          item.id +
                          "?version=" +
                          item.version +
                          "&confirmed=true",
                        "DELETE",
                      );
                      if (context.trajectory === item.id)
                        setContext({ trajectory: undefined });
                      refresh();
                    } catch (e) {
                      setError(message(e));
                    }
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {!items.length && (
              <p className="wb-muted">
                Record a leader motion and save it to create your first
                reference.
              </p>
            )}
          </div>
          <button
            disabled={!context.trajectory || recording}
            onClick={async () => {
              try {
                const item = await request(
                  "/trajectory/" + context.trajectory + "/smooth",
                  "POST",
                );
                setContext({ trajectory: item.id, run: undefined });
                setDraft(item.data);
                setSimulation(undefined);
                refresh();
              } catch (e) {
                setError(message(e));
              }
            }}
          >
            <WandSparkles size={14} />
            Create smoothed copy
          </button>
          <p className="wb-footnote">
            Nonuniform timestamps → second-order numerical velocities →
            numerical accelerations. Smoothing resamples uniformly and creates a
            new Savitzky–Golay copy; the original stays intact.
          </p>
        </section>
        <section className="wb-card wb-pad">
          <div className="wb-panel-heading">
            <h2>Dynamic follower · revision comparison</h2>
            <Activity size={17} />
          </div>
          <p className="wb-footnote">
            Kinematic replay (3D, above) copies joint angles. This panel runs
            the real OpenModelica torque-driven follower: URDF inertias,
            gravity, coupling, effort limits, and the servo parameters stored
            in each model revision (<code>Control/FollowerServoSettings.mo</code>,
            assumed values).
          </p>
          {!context.model ? (
            <p className="wb-notice">
              Open the Modelica Engineering Editor once to create an editable
              model; its revisions are compared here.
            </p>
          ) : (
            <div className="wb-revision-pick">
              {(
                [
                  ["Reference revision", referenceRevision, setReferenceRevision],
                  ["Candidate revision", candidateRevision, setCandidateRevision],
                ] as const
              ).map(([label, value, set]) => (
                <label key={label}>
                  {label}
                  <select
                    aria-label={label}
                    value={value}
                    onChange={(e) => set(e.target.value)}
                  >
                    {revisions.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.id.slice(0, 8)} · {r.data.status}
                        {workspace?.data.accepted === r.id ? " · accepted" : ""}
                        {workspace?.data.head === r.id ? " · head" : ""} ·{" "}
                        {r.name.slice(0, 48)}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </div>
          )}
          {context.model && candidateRevision && (
            <p className="wb-footnote">
              Candidate {candidateRevision.slice(0, 8)} ·{" "}
              {revisions.find((r) => r.id === candidateRevision)?.data.status || "unknown"}
              {candidateRevision === workspace?.data.head &&
                revisions.find((r) => r.id === candidateRevision)?.data.status !== "validated" && (
                  <>
                    {" "}
                    ·{" "}
                    <button
                      disabled={!!busy}
                      onClick={() =>
                        modelAction(
                          { action: "check", class_name: "ALOHA2.Experiments.RightArmReach" },
                          "OpenModelica validation of the candidate revision",
                        )
                      }
                    >
                      Validate candidate (OpenModelica)
                    </button>
                  </>
                )}
            </p>
          )}
          <div className="wb-toolbar">
            <button
              disabled={!context.trajectory || !!busy}
              onClick={() => run(1)}
              title="Only the focus joint is torque driven; faster"
            >
              Simulate {focus} axis
            </button>
            <button
              className="wb-primary"
              disabled={!context.trajectory || !!busy}
              onClick={() => run(6)}
            >
              Simulate six axes
            </button>
          </div>
          {!context.trajectory && (
            <p className="wb-muted">Select or record a leader trajectory first.</p>
          )}
          {busy && <p className="wb-notice">{busy}…</p>}
          <select
            aria-label="Saved follower simulation"
            value={context.run || ""}
            onChange={async (e) => {
              if (!e.target.value) {
                setSimulation(undefined);
                setContext({ run: undefined });
                return;
              }
              try {
                const result = await request<Doc>("/record/" + e.target.value);
                setSimulation(result);
                setContext({
                  run: result.id,
                  trajectory: result.data.trajectory,
                });
                setTime(0);
                setPlaying(false);
              } catch (error) {
                setError(message(error));
              }
            }}
          >
            <option value="">Saved simulations…</option>
            {runItems.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} · {new Date(r.created).toLocaleString()}
              </option>
            ))}
          </select>
          {simulation && (
            <SimulationResult
              simulation={simulation}
              focus={simulation.data.focus || focus}
              joints={config?.joint_ids || []}
              controller={controller}
              setController={setController}
              workspace={workspace}
              revisions={revisions}
              busy={!!busy}
              onValidate={() =>
                modelAction(
                  { action: "check", class_name: "ALOHA2.Experiments.RightArmReach" },
                  "OpenModelica validation of the candidate revision",
                )
              }
              onAccept={(revision: string) =>
                modelAction({ action: "accept", revision }, "Accepting revision")
              }
              onRollback={async (revision: string) => {
                if (!context.model) return;
                const changes = await request("/model/" + context.model + "/changes");
                await modelAction(
                  { action: "restore", revision, hashes: changes.hashes },
                  "Restoring reference revision",
                );
              }}
            />
          )}
        </section>
      </div>
    </div>
  );
}
function Signal({ result }: { result: any }) {
  const values = result.ee_error_m.map((n: number) => n * 1000),
    hi = Math.max(...values, 0.001);
  return (
    <div className="wb-signal">
      <span>End-effector error · mm · actual OMC result</span>
      <svg
        viewBox="0 0 600 100"
        role="img"
        aria-label="Measured follower end-effector error"
      >
        <path
          d={values
            .map(
              (v: number, i: number) =>
                `${i ? "L" : "M"}${(i / (values.length - 1)) * 600},${90 - (v / hi) * 75}`,
            )
            .join(" ")}
          fill="none"
          stroke="#2563EB"
          strokeWidth="2"
        />
        <text x="4" y="12" fill="#92a4ba">
          {hi.toFixed(2)} mm
        </text>
      </svg>
    </div>
  );
}

function JointSignal({
  result,
  index,
  name,
}: {
  result: any;
  index: number;
  name: string;
}) {
  const reference = result.q_reference.map((row: number[]) => row[index]),
    actual = result.q_actual.map((row: number[]) => row[index]),
    lo = Math.min(...reference, ...actual),
    hi = Math.max(...reference, ...actual),
    span = Math.max(hi - lo, 0.001);
  const path = (values: number[]) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${(i / (values.length - 1)) * 600},${90 - ((v - lo) / span) * 75}`,
      )
      .join(" ");
  return (
    <div className="wb-signal">
      <span>{name} · joint tracking · rad</span>
      <svg
        viewBox="0 0 600 110"
        role="img"
        aria-label="Mapped leader reference and measured follower joint angle"
      >
        <path
          d={path(reference)}
          fill="none"
          stroke="#0D9488"
          strokeWidth="2"
        />
        <path d={path(actual)} fill="none" stroke="#2563EB" strokeWidth="2" />
        <text x="4" y="12" fill="#8da5bd">
          {hi.toFixed(3)} rad
        </text>
        <text x="4" y="107" fill="#8da5bd">
          {lo.toFixed(3)} rad
        </text>
      </svg>
      <p className="wb-footnote">
        Teal: mapped leader reference · Blue: torque-driven follower response
      </p>
    </div>
  );
}

const SLEW_JOINT_RAD_PER_S = 1.2,
  SLEW_GRIPPER_M_PER_S = 0.03,
  APPROACH_HEIGHT_M = 0.08;
const GUIDED_IDS = GUIDED_STEPS.map((s) => s.id);

/** Manipulator end effector of a /pose response in the scenario's frame. */
function scenarioEE(sc: any, lay: Layout, p: any): number[] | null {
  const role: Role = sc.manipulator?.role === "leader" ? "leader" : "follower";
  const ee = p[role]?.ee_gripper_link?.slice(0, 3);
  if (!ee) return null;
  if (!sc.frame?.layout) {
    // Legacy scenario: follower base frame only; a leader point must never be used there.
    return role === "follower" ? ee : null;
  }
  return [...toWorld(lay, role, local(role, ee))];
}

/** Scenario-frame task objects -> STUDIO_DISPLAY_WORLD for the renderer. */
function sceneToWorld(scene: SceneState, sc: any, lay: Layout): SceneState {
  const w = (p: number[]): number[] =>
    sc.frame?.layout ? [...world(p)] : [...toWorld(lay, "follower", local("follower", p))];
  return { ...scene, cube: w(scene.cube), marker: w(scene.marker), target: { ...scene.target, center: w(scene.target.center) } };
}

function FrameIndicator({
  lay,
  scenario,
  layoutName,
  setLayoutName,
  disabled,
}: {
  lay: Layout;
  scenario: any;
  layoutName: string;
  setLayoutName: (n: string) => void;
  disabled: boolean;
}) {
  const fmt = (p: readonly number[]) => "(" + p.map((v) => (Math.abs(v) < 5e-7 ? 0 : v).toFixed(3)).join(", ") + ")";
  const rows: [string, number[]][] = scenario
    ? [
        ["Cube A (centre)", scenario.objects[0].start_m],
        ["Target B (centre)", scenario.targets[0].center_m],
      ]
    : [];
  const asWorld = (p: number[]) =>
    scenario?.frame?.layout ? world(p) : toWorld(lay, "follower", local("follower", p));
  return (
    <section className="wb-frame-indicator" aria-label="Workspace frames">
      <div className="wb-frame-head">
        <strong>{lay.status === "EXPERIMENTAL_DISPLAY" ? EXPERIMENTAL_NOTICE : "Legacy display layout — task scene in the follower frame; leader cannot reach A/B"}</strong>
        <label>
          Layout{" "}
          <select aria-label="Display layout" value={layoutName} disabled={disabled} onChange={(e) => setLayoutName(e.target.value)}>
            {LAYOUT_NAMES.map((n) => (
              <option key={n} value={n}>
                {loadLayout(n).label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <table className="wb-table">
        <thead>
          <tr>
            <th>Point · metres</th>
            <th>Display world</th>
            <th>Leader base (local)</th>
            <th>Follower base (local)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, p]) => {
            const w = asWorld(p);
            return (
              <tr key={name}>
                <td>{name}</td>
                <td>{fmt(w)}</td>
                <td>{fmt(toLocal(lay, "leader", w))}</td>
                <td>{fmt(toLocal(lay, "follower", w))}</td>
              </tr>
            );
          })}
          {(["leader", "follower"] as const).map((r) => (
            <tr key={r}>
              <td>{r === "leader" ? "Leader base" : "Follower base"} ({lay.bases[r].model})</td>
              <td colSpan={3}>
                origin {fmt(lay.bases[r].xyz)} · yaw {((lay.bases[r].yaw * 180) / Math.PI).toFixed(1)}°
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="wb-footnote">
        Display world = studio scene frame (Z up, table top z = 0), <strong>not a calibrated hardware frame</strong>.{" "}
        {lay.evidence}
      </p>
      <ul className="wb-gates" aria-label="Engineering gates">
        {Object.entries(GATES).map(([k, v]) => (
          <li key={k} className={v ? "open" : "closed"}>
            {v ? "✓" : "✗"} {k.replaceAll("_", " ")}
          </li>
        ))}
      </ul>
      {scenario?.manipulator?.role === "leader" && (
        <p className="wb-footnote">
          Shared table: the cube rule follows the <strong>leader</strong> gripper (your demonstration). The follower
          attempt is the joint-mapped replay of the recording, evaluated separately after saving (no retargeting yet).
        </p>
      )}
    </section>
  );
}

const DYNAMIC_JOINTS = ["waist", "shoulder", "elbow", "forearm_roll", "wrist_angle", "wrist_rotate"];

function SimulationResult({
  simulation,
  focus,
  joints,
  controller,
  setController,
  workspace,
  revisions,
  busy,
  onValidate,
  onAccept,
  onRollback,
}: {
  simulation: Doc;
  focus: string;
  joints: string[];
  controller: string;
  setController: (v: string) => void;
  workspace?: Doc;
  revisions: Doc[];
  busy: boolean;
  onValidate: () => void;
  onAccept: (revision: string) => void;
  onRollback: (revision: string) => void;
}) {
  const results = simulation.data.results || {};
  const names = Object.keys(results);
  const runs: any[] = simulation.data.runs || names.map((n) => ({ name: n, label: n }));
  const index = Math.max(0, joints.indexOf(focus));
  const ref = results.reference || results.baseline;
  const cand = results.candidate || results.improved;
  const label = (n: string) =>
    runs.find((r) => r.name === n)?.label?.split(" · ")[0] ||
    ({ baseline: "baseline (legacy)", improved: "comparison (legacy)" } as any)[n] ||
    n;
  const status = (rid?: string) => revisions.find((r) => r.id === rid)?.data.status;
  const candidateRun = runs.find((r) => r.name === "candidate");
  const referenceRun = runs.find((r) => r.name === "reference");
  const candidateStatus = status(candidateRun?.revision);
  const servo = (n: string) => results[n]?.config?.servo?.[focus];
  const rows: [string, (m: any) => number, number, string][] = [
    [`${focus} RMS error`, (m) => m.joint_rms_rad[index], 1000, "mrad"],
    [`${focus} maximum error`, (m) => m.joint_max_rad[index], 1000, "mrad"],
    ["End-effector RMS error", (m) => m.ee_rms_m, 1000, "mm"],
    ["End-effector maximum error", (m) => m.ee_max_m, 1000, "mm"],
    [`${focus} peak effort`, (m) => m.peak_effort_Nm[index], 1, "N·m"],
    ["Limit-violation samples", (m) => m.limit_violation_samples + m.velocity_limit_violation_samples, 1, ""],
  ];
  return (
    <div className="wb-sim-result">
      {ref && <TrackingComparison reference={ref} candidate={cand} index={index} name={focus} />}
      <table className="wb-table">
        <thead>
          <tr>
            <th>Measured on the same recorded reference (OpenModelica)</th>
            {names.map((n) => (
              <th key={n}>{label(n)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(([title, get, scale, unit]) => (
            <tr key={title}>
              <td>{title}</td>
              {names.map((n) => (
                <td key={n}>
                  {(get(results[n].metrics) * scale).toFixed(unit ? 2 : 0)} {unit}
                </td>
              ))}
            </tr>
          ))}
          <tr>
            <td>{focus} servo (kp · kd · lag · feed-forward)</td>
            {names.map((n) => (
              <td key={n}>
                {servo(n)
                  ? `${servo(n).kp} · ${servo(n).kd} · ${servo(n).actuatorTime} s · ${servo(n).feedforward}`
                  : results[n].config?.kp !== undefined
                    ? `${results[n].config.kp} · ${results[n].config.kd} (legacy)`
                    : "—"}
              </td>
            ))}
          </tr>
          <tr>
            <td>Revision</td>
            {names.map((n) => {
              const rid = runs.find((r) => r.name === n)?.revision;
              return (
                <td key={n}>
                  {rid ? rid.slice(0, 8) : "generated baseline"}
                  {rid && status(rid) ? ` · ${status(rid)}` : ""}
                  {rid && workspace?.data.accepted === rid ? " · accepted" : ""}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
      <p className="wb-notice">{simulation.data.conclusion}</p>
      {candidateRun?.revision && workspace && (
        <div className="wb-decision">
          <strong>Decision on candidate {candidateRun.revision.slice(0, 8)}</strong>
          <span>
            {workspace.data.accepted === candidateRun.revision
              ? "Accepted: this validated revision is now the model's reference revision."
              : candidateStatus === "validated"
              ? "OpenModelica validation passed."
              : candidateRun.revision === workspace.data.head
                ? "Not yet validated by OpenModelica."
                : "Only the head revision can be validated."}
          </span>
          <div className="wb-toolbar">
            <button
              disabled={busy || candidateStatus === "validated" || candidateRun.revision !== workspace.data.head}
              onClick={onValidate}
            >
              Validate candidate (OpenModelica)
            </button>
            <button
              className="wb-primary"
              disabled={busy || candidateStatus !== "validated" || workspace.data.accepted === candidateRun.revision}
              onClick={() => onAccept(candidateRun.revision)}
            >
              Accept candidate
            </button>
            {referenceRun?.revision && (
              <button
                disabled={busy}
                onClick={() => {
                  if (confirm("Restore the reference revision into a new working revision? The candidate stays in history."))
                    onRollback(referenceRun.revision);
                }}
              >
                Roll back to reference
              </button>
            )}
          </div>
          <small>
            Acceptance requires a validated revision and your explicit click; roll back creates a new revision and
            keeps the candidate in history.
          </small>
        </div>
      )}
      <select
        aria-label="Follower response shown in 3D playback"
        value={controller}
        onChange={(e) => setController(e.target.value)}
      >
        {names.map((n) => (
          <option key={n} value={n}>
            3D playback: {label(n)} follower response
          </option>
        ))}
      </select>
      <Signal result={results[controller] || results[names[0]]} />
      <details>
        <summary>All joint metrics, delays and limitations</summary>
        {names.map((n) => (
          <pre key={n}>{label(n) + ":\n" + JSON.stringify(results[n].metrics, null, 2)}</pre>
        ))}
        <ul>
          {(simulation.data.limitations || []).map((l: string) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function TrackingComparison({
  reference,
  candidate,
  index,
  name,
}: {
  reference: any;
  candidate?: any;
  index: number;
  name: string;
}) {
  const col = (rows: number[][]) => rows.map((r) => r[index]);
  const lead = col(reference.q_reference),
    a = col(reference.q_actual),
    b = candidate ? col(candidate.q_actual) : [];
  const all = [...lead, ...a, ...b],
    lo = Math.min(...all),
    hi = Math.max(...all),
    span = Math.max(hi - lo, 1e-4);
  const t0 = reference.time[0],
    t1 = reference.time.at(-1) || 1;
  const path = (time: number[], values: number[]) =>
    values
      .map(
        (v, i) =>
          `${i ? "L" : "M"}${(((time[i] - t0) / (t1 - t0)) * 600).toFixed(1)},${(95 - ((v - lo) / span) * 82).toFixed(1)}`,
      )
      .join(" ");
  const err = candidate
    ? candidate.q_actual.map((r: number[], i: number) => (r[index] - candidate.q_reference[i][index]) * 1000)
    : [];
  const emax = Math.max(1e-3, ...err.map(Math.abs));
  return (
    <div className="wb-signal">
      <span>{name} · leader reference vs follower responses · rad · OpenModelica</span>
      <svg viewBox="0 0 600 105" role="img" aria-label={`${name} reference and simulated follower angles`}>
        <path d={path(reference.time, lead)} fill="none" stroke="#0D9488" strokeWidth="2.5" />
        <path d={path(reference.time, a)} fill="none" stroke="#7aa7f7" strokeWidth="2" strokeDasharray="6 4" />
        {candidate && <path d={path(candidate.time, b)} fill="none" stroke="#2563EB" strokeWidth="2" />}
        <text x="4" y="11" fill="#8da5bd">{hi.toFixed(3)} rad</text>
        <text x="4" y="103" fill="#8da5bd">{lo.toFixed(3)} rad</text>
      </svg>
      <p className="wb-legend">
        <span className="leader">— leader reference (mapped)</span>
        <span className="ref">- - reference revision follower</span>
        {candidate && <span className="cand">— candidate revision follower</span>}
      </p>
      {candidate && (
        <>
          <span>{name} · candidate tracking error · mrad</span>
          <svg viewBox="0 0 600 60" role="img" aria-label="Candidate tracking error">
            <line x1="0" x2="600" y1="30" y2="30" stroke="#33465c" />
            <path
              d={err
                .map(
                  (v: number, i: number) =>
                    `${i ? "L" : "M"}${(((candidate.time[i] - t0) / (t1 - t0)) * 600).toFixed(1)},${(30 - (v / emax) * 26).toFixed(1)}`,
                )
                .join(" ")}
              fill="none"
              stroke="#2563EB"
              strokeWidth="1.5"
            />
            <text x="4" y="10" fill="#8da5bd">±{emax.toFixed(2)} mrad</text>
          </svg>
        </>
      )}
    </div>
  );
}
