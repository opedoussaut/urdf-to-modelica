/**
 * Physical AI Atlas - plain-language concepts behind the studio, organised as a map (regions → concepts).
 * Facts about the studio itself are taken from its own sources (URDF, kkh/studio/servo1d.py, ontology/, configuration);
 * nothing here reports a result that the studio has not produced.
 */
export type RegionId = "start" | "machine" | "physics" | "knowledge" | "learning" | "reality";
export type Visual =
  | "sense-act"
  | "arm-explore"
  | "arm-swing"
  | "servo-loop"
  | "twin"
  | "modelica-1d"
  | "provenance"
  | "ontology"
  | "leader-follower"
  | "grounding"
  | "sim2real";

export type Concept = {
  id: string;
  region: RegionId;
  title: string;
  /** The idea in one sentence. */
  gist: string;
  /** Markdown paragraphs. */
  body: string;
  visual: Visual;
  /** Where to see it in the studio: page index (App tabs) and what you will find there. */
  studio: { page: number; label: string; what: string }[];
  related: string[];
};

export const REGIONS: { id: RegionId; label: string; blurb: string; color: string }[] = [
  { id: "start", label: "Start here", blurb: "What Physical AI is", color: "#1d4ed8" },
  { id: "machine", label: "The machine", blurb: "Parts and motion", color: "#0f766e" },
  { id: "physics", label: "Physics & models", blurb: "Forces, control, simulation", color: "#0369a1" },
  { id: "knowledge", label: "Knowledge", blurb: "Facts you can trust", color: "#6d28d9" },
  { id: "learning", label: "Learning & AI", blurb: "Teaching and asking", color: "#b45309" },
  { id: "reality", label: "Reality check", blurb: "Our challenge", color: "#b42318" },
];

export const CONCEPTS: Concept[] = [
  {
    id: "physical-ai",
    region: "start",
    title: "What is Physical AI?",
    gist: "AI that does not only answer - it senses the real world, decides, and moves something in it.",
    body: `A chatbot produces text. **Physical AI** produces *actions*: a robot arm picks up a cup, a car brakes, a drone lands. It runs a loop again and again: **sense** (cameras, joint encoders), **decide** (a controller or a learned policy), **act** (motors).

The difference that matters: in the physical world, mistakes have mass. A wrong word can be corrected; a wrong torque can break a gripper or hurt someone. That is why Physical AI needs more than a clever model - it needs to respect **physics**: limits, inertia, gravity, friction.

This studio works on the robot used by much of today's research on learned manipulation, **ALOHA 2** (two small arms you can teach by demonstration). Its idea: before trusting any change on the real robot, test it on an **engineering model** whose every number has a known source.`,
    visual: "sense-act",
    studio: [{ page: 4, label: "Guided demo", what: "the whole flow on one joint, from specification to approved change" }],
    related: ["anatomy", "twin", "sim2real"],
  },
  {
    id: "anatomy",
    region: "machine",
    title: "Anatomy of a robot arm",
    gist: "An arm is a chain of rigid parts (links) connected by motorised hinges (joints).",
    body: `Think of your own arm: bones are **links**, the shoulder, elbow and wrist are **joints**. A robot arm is the same chain, from a fixed **base** to an end tool - here a two-finger **gripper**.

Each joint adds one way of moving, a **degree of freedom**. The ALOHA follower arm (a ViperX 300) has **six** joints - base rotation, shoulder, elbow, forearm twist, wrist, wrist twist - plus the gripper. Six is the minimum to place a tool at any position *and* orientation within reach. The shoulder and elbow carry the most load, so each is driven by **two motors** working together.

All of this is written down by the manufacturer in a file called a **URDF** (Unified Robot Description Format): every link's mass and shape, every joint's axis and limits. The studio reads that file as its single source for the robot's geometry.`,
    visual: "arm-explore",
    studio: [{ page: 0, label: "Robot & motion", what: "move each joint of the leader arm and watch the follower" }],
    related: ["kinematics", "ontology"],
  },
  {
    id: "kinematics",
    region: "machine",
    title: "How an arm moves: kinematics",
    gist: "Joint angles decide where the gripper ends up - and limits decide where it can never go.",
    body: `**Forward kinematics** answers: *if each joint is at this angle, where is the gripper?* You chain the links one after another, each turned by its joint. It always has exactly one answer.

**Inverse kinematics** asks the opposite: *I want the gripper here - which joint angles get it there?* It may have several answers, or none (the point is out of reach). The studio's "drag the end effector" tool solves it step by step, respecting the limits.

**Joint limits** are the angles a joint may not pass - mechanical stops or cable constraints, written in the URDF. They are small numbers with big consequences: a limit typed in degrees where the model expects radians makes the arm "allowed" to rotate 57 times too far. Catching that kind of mistake automatically is one of the jobs of the knowledge layer.

Kinematics is geometry only. It says *where*, not *how hard* - for that you need forces.`,
    visual: "arm-swing",
    studio: [{ page: 0, label: "Robot & motion", what: "joint sliders, end-effector dragging, recorded motions" }],
    related: ["anatomy", "control", "provenance"],
  },
  {
    id: "control",
    region: "physics",
    title: "Motors, forces and control",
    gist: "A servo motor keeps measuring the error to its target and pushes to reduce it.",
    body: `To move a link, a motor must produce **torque** - enough to accelerate the link's **inertia** and hold it against **gravity** and **friction**. The further and heavier the arm stretches out, the more torque it takes just to stay still.

Robot joints use **servo control**: a target angle comes in, a sensor measures the actual angle, and the controller pushes in proportion to the **error** (gain *kp*) while braking in proportion to the speed difference (gain *kd*). Strong gains follow the target tightly but can overshoot and shake; weak gains are smooth but lag behind. The motor can only deliver so much torque - beyond that it **saturates**.

Tuning these settings is a classic engineering trade-off, and a good place to start understanding why a physics model is useful: you can try ten settings in simulation in the time it takes to test one on hardware.`,
    visual: "servo-loop",
    studio: [{ page: 5, label: "Joint simulation", what: "change kp/kd for one joint and compare tracking error, torque and settling" }],
    related: ["modelica-1d", "twin", "sim2real"],
  },
  {
    id: "twin",
    region: "physics",
    title: "Digital twin vs animation",
    gist: "An animation shows motion; a physics model computes it - and can answer “what if?”.",
    body: `A 3D animation replays positions someone gave it. It cannot tell you whether the motor was strong enough, how far the arm overshot, or what happens with a heavier gripper.

A **physics model** contains the equations of motion: masses, inertias, joint axes, motors and controllers. You give it inputs (a target motion, a setting) and it **computes** the result - angles, speeds, torques over time. Change one parameter and run it again: that is a **virtual experiment**.

A **digital twin** is such a model kept faithful to one real machine: its parameters come from that machine's documentation and measurements, and its predictions are checked against what the machine actually does. The studio builds the model automatically from the URDF and keeps a trace of where every parameter came from. Whether it deserves the word *twin* is decided by comparison with the real robot - see *sim-to-real*.`,
    visual: "twin",
    studio: [
      { page: 6, label: "Generate model", what: "URDF → Modelica model, checked by OpenModelica" },
      { page: 1, label: "Model editor", what: "the model as code, with versions and approvals" },
    ],
    related: ["modelica-1d", "sim2real", "provenance"],
  },
  {
    id: "modelica-1d",
    region: "physics",
    title: "1D simulation, Modelica and Dymola",
    gist: "System simulation connects physical components like real parts and lets the tool solve the equations.",
    body: `**1D simulation** (also called *system simulation*) describes a machine as connected components - a motor, a gearbox, an inertia, a spring, a controller - each with a few parameters, and computes how they behave **over time**. It does not mesh the 3D shape of each part (that is *3D CAE*: finite elements, fluid dynamics). The payoff: a whole system runs in seconds, so you can test many designs and control settings early.

**Modelica** is an open language for exactly this, maintained by the non-profit Modelica Association. You write **equations**, not step-by-step code, and you connect components the way you would wire real parts: a motor flange to a gear, a gear to a load. The tool works out the order of computation. The free **Modelica Standard Library** provides mechanics, electrics, thermal and control blocks.

Two tools run Modelica: **OpenModelica**, open-source, used by this studio on your computer; and **Dymola**, a widely used commercial environment from Dassault Systèmes. Both read the same language, so standard models are meant to move between them - the studio's generated package uses only the standard library, but it has not been tested in Dymola here.

In the studio, the whole arm is a Modelica **multibody** model (3D mechanics as a system model), and *Joint simulation* is a pure **1D** model of one joint: inertia, damping, gravity and friction torque, and the servo.`,
    visual: "modelica-1d",
    studio: [
      { page: 5, label: "Joint simulation", what: "a 1D servo model of one joint, simulated by OpenModelica" },
      { page: 1, label: "Model editor", what: "the generated Modelica package and its kinematic schematic" },
    ],
    related: ["control", "twin", "ontology"],
  },
  {
    id: "provenance",
    region: "knowledge",
    title: "Knowing what you know",
    gist: "Every number in an engineering model should say where it comes from and how sure we are.",
    body: `A model is only as trustworthy as its numbers. The studio labels each one:

- **Verified** - read directly from a pinned public source (the manufacturer's URDF, a datasheet).
- **Derived** - computed from verified values by a stated method (e.g. the equivalent inertia of a joint).
- **Assumed** - chosen by the project because nobody measured it yet (e.g. servo gains). Safe to tune, never to be confused with a fact.
- **Simulated** - the output of a real OpenModelica run, linked to the exact model version.

This record of origin is called **provenance**. It protects you from the most common modelling failure: an assumption that silently becomes a "fact" three files later. It also makes reviews faster - a reviewer looks at the assumptions, not at everything.`,
    visual: "provenance",
    studio: [{ page: 7, label: "Engineering reasoning", what: "one joint traced from source file to decision, every fact labelled" }],
    related: ["ontology", "sim2real", "trust"],
  },
  {
    id: "ontology",
    region: "knowledge",
    title: "Ontologies and knowledge graphs - and why we use them",
    gist: "A shared vocabulary with rules, so robot facts from different files mean the same thing to people, tools and AI.",
    body: `The same elbow appears in the URDF, in the Modelica model, in a datasheet, in a test report. Each uses its own names and units. An **ontology** is an agreed vocabulary with rules - *a joint connects two links; a joint limit is an angle; an angle has a unit* - written so that a computer can check it.

A **knowledge graph** stores the facts using that vocabulary, as a network: *elbow* -is a→ *revolute joint*; *elbow* -has upper limit→ *1.6 rad*; that value -comes from→ *the URDF file at this commit*. The studio uses public standards rather than inventing its own words: **CORA** (the IEEE 1872 robotics ontology), **QUDT** for quantities and units, **PROV-O** (W3C) for provenance, and **SHACL** rules to check the data. The graph lives in **GraphDB** on this computer.

**Why we propose it:**
1. **One meaning across tools** - the URDF, the Modelica model and the documentation are linked element by element.
2. **Mistakes caught by rules** - a limit in the wrong unit, a missing mass, a parameter outside its declared bounds are flagged automatically.
3. **Grounded AI** - the assistant answers from retrieved facts with sources, not from memory. Whether this measurably improves AI-assisted modelling is the research question the studio is built to test.`,
    visual: "ontology",
    studio: [
      { page: 3, label: "Knowledge graph", what: "browse the robot's entities and their sources" },
      { page: 7, label: "Engineering reasoning", what: "the rules that check each value" },
    ],
    related: ["provenance", "trust", "modelica-1d"],
  },
  {
    id: "demonstrations",
    region: "learning",
    title: "Learning from demonstrations",
    gist: "A person moves a leader arm; the robot's follower arm copies it - and the recordings become training data.",
    body: `ALOHA was designed for **teleoperation**: a person moves a small **leader** arm (here a WidowX 250) by hand, and the **follower** arm (the ViperX 300 that does the work) mirrors it joint by joint. Every movement is recorded - joint angles, gripper, camera images.

Many recorded demonstrations of a task are then used to train a **policy**: a neural network that maps what the robot sees to what it should do next. ALOHA's original work introduced **ACT** (Action Chunking with Transformers), which predicts short sequences of actions at once. This is **imitation learning** - learning by watching, rather than by trial and error.

What the studio does today: you record leader motions, replay them on the follower, and simulate the follower's response with its physics model. It **does not train a policy** - it focuses on the engineering model that a learned policy would ultimately run on.`,
    visual: "leader-follower",
    studio: [{ page: 0, label: "Robot & motion", what: "record a leader demonstration and replay it on the follower" }],
    related: ["sim2real", "kinematics", "trust"],
  },
  {
    id: "trust",
    region: "learning",
    title: "AI you can trust",
    gist: "A language model may sound right while guessing. Grounding and human approval keep it honest.",
    body: `Large language models are fluent - and that is the danger: a confident answer about a joint limit may be invented. In engineering, the cost of a plausible wrong number is high.

Three habits make AI useful here:
- **Grounding** - before answering, the assistant retrieves the relevant facts (from the knowledge graph and source files) and must cite them. You can compare an answer *with* and *without* this evidence side by side.
- **Bounded tools** - the AI can read and propose, never change the model by itself. Proposed parameter changes are checked against declared bounds and limited to tunable settings, not manufacturer facts.
- **Human approval** - a proposal becomes a new model version only after a passing OpenModelica check and a person accepting it.

The model runs **locally** (NVIDIA Nemotron through Ollama): no robot data leaves the computer.`,
    visual: "grounding",
    studio: [{ page: 2, label: "AI assistant", what: "the same question answered with and without the knowledge graph" }],
    related: ["ontology", "provenance"],
  },
  {
    id: "sim2real",
    region: "reality",
    title: "The sim-to-real gap - our challenge",
    gist: "A simulation is right only about what it models. The gap is everything else - and we have to measure it.",
    body: `A controller tuned in simulation, or a policy trained there, often behaves differently on the real robot. This **sim-to-real gap** comes from what the model leaves out or gets wrong:

- **Unmeasured parameters** - in this studio the servo gains and motor lag are *assumed*, and the URDF damping is a generic default, not identified on hardware.
- **Missing effects** - the joint model states what it does not include: motor rotor inertia through the gearbox, backlash, flexibility, payload, and how the two shoulder motors share the load.
- **Contact** - grasping and collisions are not modelled; the cube task is a visual scene, not physics.
- **Calibration** - where the arms stand relative to each other in the 3D scene is a display convention, not measured on the real cell.

Ways to close it: **system identification** (measure the real joint's response and fit the parameters), **validation** (compare recorded real motions with simulated ones), and for learned policies, **domain randomisation** (train across a range of plausible parameters). The precondition for all of them is what the studio already enforces: every parameter labelled *verified, derived or assumed*, so you know exactly what to measure next.

**This is our challenge:** turn the engineering model from a well-sourced estimate into a validated twin of the real ALOHA, one measured parameter at a time.`,
    visual: "sim2real",
    studio: [
      { page: 5, label: "Joint simulation", what: "see which parameters are derived and which are assumed" },
      { page: 7, label: "Engineering reasoning", what: "assumptions listed explicitly, per joint" },
    ],
    related: ["provenance", "twin", "control", "demonstrations"],
  },
];

export const ROUTE = CONCEPTS.map((c) => c.id);
export const conceptById = (id?: string | null) => CONCEPTS.find((c) => c.id === id);
