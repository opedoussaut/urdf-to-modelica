/**
 * Physical AI Atlas - plain-language concepts behind the studio, organised as a map (regions → concepts).
 * Facts about the studio itself are taken from its own sources (URDF, kkh/studio/servo1d.py, ontology/, configuration);
 * nothing here reports a result that the studio has not produced.
 *
 * Definitions: each one names its source. `quote: true` means the wording is the source's own (short definitional
 * quotes, checked against the source on 2026-10-20); otherwise the text is a close paraphrase and is shown as such.
 */
export type RegionId = "start" | "machine" | "physics" | "knowledge" | "learning" | "reality";
export type Visual =
  | "sense-act"
  | "ai-kinds"
  | "arm-explore"
  | "chain"
  | "arm-swing"
  | "planar-fk"
  | "joint-limits"
  | "servo-loop"
  | "effort"
  | "gains"
  | "twin"
  | "twin-levels"
  | "modelica-1d"
  | "acausal"
  | "tools"
  | "three-ways"
  | "provenance"
  | "prov-o"
  | "ontology"
  | "semantic-stack"
  | "leader-follower"
  | "lfd-pipeline"
  | "chunking"
  | "grounding"
  | "rag"
  | "fm-outputs"
  | "bench-vs-studio"
  | "sim2real"
  | "close-gap"
  | "vv";

export type Definition = {
  term: string;
  text: string;
  /** true: the source's own words (shown in quotation marks); false: a faithful paraphrase. */
  quote?: boolean;
  source: string;
  url?: string;
  /** Optional remark on status or scope of the definition. */
  note?: string;
};

export type Concept = {
  id: string;
  region: RegionId;
  title: string;
  /** The idea in one sentence. */
  gist: string;
  /** Reference definitions, most important first. */
  definitions: Definition[];
  /** Markdown paragraphs. */
  body: string;
  /** Figures, in display order (first one is the lead visual). */
  visuals: Visual[];
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

const ISO8373 = { source: "ISO 8373:2021, Robotics - Vocabulary", url: "https://www.iso.org/obp/ui/#iso:std:iso:8373:ed-3:v1:en" };
const MR = { source: "Lynch & Park, Modern Robotics (Cambridge University Press, 2017)", url: "https://hades.mech.northwestern.edu/index.php/Modern_Robotics" };
const AM = { source: "Åström & Murray, Feedback Systems, 2nd ed. (Princeton University Press, 2021)", url: "https://www.cds.caltech.edu/~murray/amwiki/" };

export const CONCEPTS: Concept[] = [
  {
    id: "physical-ai",
    region: "start",
    title: "What is Physical AI?",
    gist: "AI that does not only answer - it senses the real world, decides, and moves something in it.",
    definitions: [
      {
        term: "Physical AI",
        text: "AI that lets autonomous systems such as robots, self-driving cars and cameras perceive, understand and reason about the real world, and perform or orchestrate complex actions in it.",
        source: "NVIDIA Glossary, “What is Physical AI?”",
        url: "https://www.nvidia.com/en-us/glossary/generative-physical-ai/",
        note: "No standards body defines the term yet; this is the industry definition that popularised it. Research literature also says embodied AI.",
      },
      { term: "Robot", text: "programmed actuated mechanism with a degree of autonomy to perform locomotion, manipulation or positioning", quote: true, ...ISO8373 },
      { term: "Autonomy", text: "ability to perform intended tasks based on current state and sensing, without human intervention", quote: true, ...ISO8373 },
    ],
    body: `A chatbot produces text. **Physical AI** produces *actions*: a robot arm picks up a cup, a car brakes, a drone lands. It runs a loop again and again: **sense** (cameras, joint encoders), **decide** (a controller or a learned policy), **act** (motors).

The difference that matters: in the physical world, mistakes have mass. A wrong word can be corrected; a wrong torque can break a gripper or hurt someone. That is why Physical AI needs more than a clever model - it needs to respect **physics**: limits, inertia, gravity, friction.

This studio works on the robot used by much of today's research on learned manipulation, **ALOHA 2** (two small arms you can teach by demonstration). Its idea: before trusting any change on the real robot, test it on an **engineering model** whose every number has a known source.`,
    visuals: ["sense-act", "ai-kinds"],
    studio: [{ page: 4, label: "Guided demo", what: "the whole flow on one joint, from specification to approved change" }],
    related: ["anatomy", "twin", "sim2real"],
  },
  {
    id: "anatomy",
    region: "machine",
    title: "Anatomy of a robot arm",
    gist: "An arm is a chain of rigid parts (links) connected by motorised hinges (joints).",
    definitions: [
      {
        term: "Manipulator",
        text: "A mechanism made of a series of segments, jointed or sliding relative to one another, whose function is to grasp and move objects (parts or tools), usually in several degrees of freedom.",
        ...ISO8373,
      },
      { term: "Degrees of freedom", text: "The smallest number of real-valued coordinates needed to represent the robot's configuration.", ...MR },
      { term: "End effector", text: "A device designed to be attached to the robot's mechanical interface so that the robot can perform its task - here, the gripper.", ...ISO8373 },
      { term: "URDF", text: "The Unified Robot Description Format (URDF) is an XML specification to describe a robot.", quote: true, source: "ROS documentation, urdf/XML", url: "https://wiki.ros.org/urdf/XML/model" },
    ],
    body: `Think of your own arm: bones are **links**, the shoulder, elbow and wrist are **joints**. A robot arm is the same chain, from a fixed **base** to an end tool - here a two-finger **gripper**.

Each joint adds one way of moving, a **degree of freedom**. The ALOHA follower arm (a ViperX 300 S) has **six** joints - base rotation, shoulder, elbow, forearm twist, wrist, wrist twist - plus the gripper. Six is the minimum to place a tool at any position *and* orientation within reach. The shoulder and elbow carry the most load, so each is driven by **two motors** working together.

All of this is written down by the manufacturer in a **URDF** file: every link's mass and shape, every joint's axis and limits. URDF can only describe tree-shaped chains of rigid links - which is exactly what this arm is. The studio reads that file as its single source for the robot's geometry.`,
    visuals: ["arm-explore", "chain"],
    studio: [{ page: 0, label: "Robot & motion", what: "move each joint of the leader arm and watch the follower" }],
    related: ["kinematics", "ontology"],
  },
  {
    id: "kinematics",
    region: "machine",
    title: "How an arm moves: kinematics",
    gist: "Joint angles decide where the gripper ends up - and limits decide where it can never go.",
    definitions: [
      { term: "Forward kinematics", text: "The forward kinematics of a robot refers to the calculation of the position and orientation of its end-effector frame from its joint coordinates θ.", quote: true, ...MR },
      { term: "Inverse kinematics", text: "Given a desired end-effector position and orientation, find the joint coordinates that achieve it. There may be several solutions, or none.", ...MR },
      { term: "Workspace", text: "The set of end-effector configurations the robot can reach.", ...MR },
      {
        term: "Joint limit",
        text: "The <limit> element of a URDF joint: lower and upper position (radians for revolute joints, metres for prismatic ones), maximum effort and maximum velocity.",
        source: "ROS documentation, urdf/XML/joint",
        url: "https://wiki.ros.org/urdf/XML/joint",
      },
    ],
    body: `**Forward kinematics** answers: *if each joint is at this angle, where is the gripper?* You chain the links one after another, each turned by its joint. It always has exactly one answer. Try it in the side view below: the lengths and limits are the real ones from the ViperX URDF.

**Inverse kinematics** asks the opposite: *I want the gripper here - which joint angles get it there?* It may have several answers ("elbow up" or "elbow down"), or none (the point is out of reach). The studio's "drag the end effector" tool solves it step by step, respecting the limits.

**Joint limits** are the angles a joint may not pass - mechanical stops or cable constraints, written in the URDF. They are small numbers with big consequences: a limit typed in degrees where the model expects radians makes the arm "allowed" to rotate 57 times too far. Catching that kind of mistake automatically is one of the jobs of the knowledge layer.

Kinematics is geometry only. It says *where*, not *how hard* - for that you need forces.`,
    visuals: ["planar-fk", "joint-limits", "arm-swing"],
    studio: [{ page: 0, label: "Robot & motion", what: "joint sliders, end-effector dragging, recorded motions" }],
    related: ["anatomy", "control", "provenance"],
  },
  {
    id: "control",
    region: "physics",
    title: "Motors, forces and control",
    gist: "A servo motor keeps measuring the error to its target and pushes to reduce it.",
    definitions: [
      { term: "Feedback", text: "A situation in which two (or more) dynamical systems are connected together such that each system influences the other.", ...AM },
      { term: "PID / PD control", text: "A control law whose action is the sum of a term proportional to the error, a term proportional to its integral and a term proportional to its derivative. PD control keeps only the proportional and derivative terms.", ...AM },
      { term: "Actuator saturation", text: "The actuator cannot deliver more than a maximum output; beyond it the commanded action is clipped and the loop no longer behaves linearly.", ...AM },
      { term: "Torque", text: "The rotational effect of a force about an axis (moment of force); SI unit newton metre (N·m).", source: "ISO 80000-4:2019, Quantities and units - Mechanics", url: "https://www.iso.org/standard/64977.html" },
    ],
    body: `To move a link, a motor must produce **torque** - enough to accelerate the link's **inertia** and hold it against **gravity** and **friction**. The further and heavier the arm stretches out, the more torque it takes just to stay still. That is why the shoulder, which carries everything after it, is the strongest joint.

Robot joints use **servo control**: a target angle comes in, a sensor measures the actual angle, and the controller pushes in proportion to the **error** (gain *kp*) while braking in proportion to the speed difference (gain *kd*). Strong gains follow the target tightly but can overshoot and shake; weak gains are smooth but lag behind. The motor can only deliver so much torque - beyond that it **saturates**.

Tuning these settings is a classic engineering trade-off, and a good place to start understanding why a physics model is useful: you can try ten settings in simulation in the time it takes to test one on hardware.`,
    visuals: ["servo-loop", "gains", "effort"],
    studio: [{ page: 5, label: "Joint simulation", what: "change kp/kd for one joint and compare tracking error, torque and settling" }],
    related: ["modelica-1d", "twin", "sim2real"],
  },
  {
    id: "twin",
    region: "physics",
    title: "Digital twin vs animation",
    gist: "An animation shows motion; a physics model computes it - and can answer “what if?”.",
    definitions: [
      {
        term: "Digital twin",
        text: "digital representation of a target entity with data connections that enable convergence between the physical and digital states at an appropriate rate of synchronization",
        quote: true,
        source: "ISO/IEC 30173:2023, Digital twin - Concepts and terminology",
        url: "https://www.iso.org/obp/ui/#iso:std:iso-iec:30173:ed-1:v1:en",
      },
      {
        term: "Digital model, shadow, twin",
        text: "Three levels told apart by data flow: a digital model exchanges data with the real object only by hand; a digital shadow is updated automatically from the real object; a digital twin exchanges data automatically in both directions.",
        source: "Kritzinger et al., Digital Twin in manufacturing, IFAC-PapersOnLine 51(11), 2018",
        url: "https://doi.org/10.1016/j.ifacol.2018.08.474",
      },
    ],
    body: `A 3D animation replays positions someone gave it. It cannot tell you whether the motor was strong enough, how far the arm overshot, or what happens with a heavier gripper.

A **physics model** contains the equations of motion: masses, inertias, joint axes, motors and controllers. You give it inputs (a target motion, a setting) and it **computes** the result - angles, speeds, torques over time. Change one parameter and run it again: that is a **virtual experiment**.

A **digital twin** goes one step further: the model stays connected to one real machine, and the two are kept in step with data. By the definitions above, what the studio has today is a **digital model** - its parameters come from documentation, and data from the real robot does not yet flow into it automatically. It is built automatically from the URDF and keeps a trace of where every parameter came from. Becoming a twin is the road described in *sim-to-real*.`,
    visuals: ["twin", "twin-levels"],
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
    definitions: [
      { term: "Modelica", text: "Modelica is an object oriented language to model cyber-physical systems.", quote: true, source: "Modelica Association, modelica.org", url: "https://modelica.org/" },
      {
        term: "Acausal (equation-based) modelling",
        text: "Components are described by equations with no fixed input/output direction; connecting them adds equations, and the tool decides the order in which unknowns are computed.",
        source: "Modelica Language Specification",
        url: "https://specification.modelica.org/",
      },
      {
        term: "FMI",
        text: "The Functional Mock-up Interface is a free standard that defines a container and an interface to exchange dynamic simulation models, distributed as a ZIP file (an FMU).",
        source: "Modelica Association Project FMI, fmi-standard.org",
        url: "https://fmi-standard.org/",
      },
    ],
    body: `**1D simulation** (also called *system simulation*) describes a machine as connected components - a motor, a gearbox, an inertia, a spring, a controller - each with a few parameters, and computes how they behave **over time**. It does not mesh the 3D shape of each part (that is *3D CAE*: finite elements, fluid dynamics). The payoff: a whole system runs in seconds, so you can test many designs and control settings early.

**Modelica** is an open language for exactly this, maintained by the non-profit Modelica Association. You write **equations**, not step-by-step code, and you connect components the way you would wire real parts: a motor flange to a gear, a gear to a load. The tool works out the order of computation. The free **Modelica Standard Library** provides mechanics, electrics, thermal and control blocks.

Two tools run Modelica: **OpenModelica**, open-source, used by this studio on your computer; and **Dymola**, a widely used commercial environment from Dassault Systèmes. Both read the same language, so standard models are meant to move between them - the studio's generated package uses only the standard library, but it has not been tested in Dymola here. Models can also be exported as **FMUs** to run inside other tools.

In the studio, the whole arm is a Modelica **multibody** model (3D mechanics as a system model), and *Joint simulation* is a pure **1D** model of one joint: inertia, damping, gravity and friction torque, and the servo.`,
    visuals: ["modelica-1d", "acausal", "tools"],
    studio: [
      { page: 5, label: "Joint simulation", what: "a 1D servo model of one joint, simulated by OpenModelica" },
      { page: 1, label: "Model editor", what: "the generated Modelica package and its kinematic schematic" },
    ],
    related: ["control", "twin", "ontology"],
  },
  {
    id: "three-ways",
    region: "physics",
    title: "Three ways to build a model from a robot file",
    gist: "A rule-based converter, an AI on its own, or an AI given the right building blocks - and the same checks for all three.",
    definitions: [
      {
        term: "URDFModelica",
        text: "A free open-source Modelica library from DLR whose Python script translates a URDF robot description into Modelica syntax and builds a package to simulate the robot.",
        source: "DLR-RM, URDFModelica README (2nd prize, Library Award, 16th International Modelica & FMI Conference, 2025)",
        url: "https://github.com/DLR-RM/urdfmodelica",
      },
      {
        term: "Retrieval-augmented generation (RAG)",
        text: "Language generation by models that combine pre-trained parametric and non-parametric memory: the model's own weights plus documents retrieved for each request.",
        source: "Lewis et al., NeurIPS 2020",
        url: "https://arxiv.org/abs/2005.11401",
      },
      {
        term: "BM25",
        text: "A ranking function for keyword search: a document scores higher when it contains the query's words often, when those words are rare in the collection, and less so as the document gets longer.",
        source: "Robertson & Zaragoza, The Probabilistic Relevance Framework: BM25 and Beyond, Foundations and Trends in Information Retrieval 3(4), 2009",
        url: "https://doi.org/10.1561/1500000019",
      },
    ],
    body: `A robot's URDF file lists its parts, joints, sizes and masses. A physics simulator needs the same robot as a **Modelica model**. The studio compares three ways to get there:

1. **AI only** - a local language model reads the URDF and writes the whole Modelica file itself. It knows Modelica only from what it saw during training.
2. **AI + library search** - the same model, but first handed the real definitions of the building blocks it needs (World, Body, Revolute joint…), found by **keyword search** (BM25) in the Modelica Standard Library installed on this computer. This is **retrieval-augmented generation**.
3. **URDFModelica** - a published, **rule-based converter** from DLR. No AI: the same file always gives the same model.

All three are judged by the **same seven checks**, run by OpenModelica: is there a file, can it be read, is it a complete model, does it run, are all parts and joints in it, does its geometry match the URDF, are axes and masses right. The two AI methods get identical settings and two chances to repair their file using OpenModelica's error messages; they never see the expected answer.

What to expect: rule-based converters are reliable within their rules but can miss details (here, URDFModelica does not enforce the gripper's mirrored fingers). Small local AIs often write code that only looks like Modelica. Grounding the AI in real library definitions is meant to close that gap - the comparison measures whether it does.`,
    visuals: ["three-ways"],
    studio: [{ page: 6, label: "Generate model", what: "the studio's own deterministic converter, checked by OpenModelica" }],
    related: ["modelica-1d", "trust", "benchmarks"],
  },
  {
    id: "provenance",
    region: "knowledge",
    title: "Knowing what you know",
    gist: "Every number in an engineering model should say where it comes from and how sure we are.",
    definitions: [
      {
        term: "Provenance",
        text: "Provenance is information about entities, activities, and people involved in producing a piece of data or thing, which can be used to form assessments about its quality, reliability or trustworthiness.",
        quote: true,
        source: "W3C PROV-DM Recommendation, 2013",
        url: "https://www.w3.org/TR/prov-dm/",
      },
      {
        term: "Entity, activity, agent",
        text: "The three core types of PROV: an entity is a thing (a file, a value); an activity is something that happens over time and uses or generates entities; an agent bears responsibility for an activity or entity.",
        source: "W3C PROV-O ontology, 2013",
        url: "https://www.w3.org/TR/prov-o/",
      },
    ],
    body: `A model is only as trustworthy as its numbers. The studio labels each one:

- **Verified** - read directly from a pinned public source (the manufacturer's URDF, a datasheet).
- **Derived** - computed from verified values by a stated method (e.g. the equivalent inertia of a joint).
- **Assumed** - chosen by the project because nobody measured it yet (e.g. servo gains). Safe to tune, never to be confused with a fact.
- **Simulated** - the output of a real OpenModelica run, linked to the exact model version.

This record of origin is **provenance**, and the studio stores it with the W3C standard vocabulary for it (PROV-O). It protects you from the most common modelling failure: an assumption that silently becomes a "fact" three files later. It also makes reviews faster - a reviewer looks at the assumptions, not at everything.`,
    visuals: ["provenance", "prov-o"],
    studio: [{ page: 7, label: "Engineering reasoning", what: "one joint traced from source file to decision, every fact labelled" }],
    related: ["ontology", "sim2real", "trust"],
  },
  {
    id: "ontology",
    region: "knowledge",
    title: "Ontologies and knowledge graphs - and why we use them",
    gist: "A shared vocabulary with rules, so robot facts from different files mean the same thing to people, tools and AI.",
    definitions: [
      {
        term: "Ontology",
        text: "a formal, explicit specification of a shared conceptualization",
        quote: true,
        source: "Studer, Benjamins & Fensel, Data & Knowledge Engineering 25, 1998 (building on Gruber, 1993)",
        url: "https://doi.org/10.1016/S0169-023X(97)00056-6",
      },
      {
        term: "Knowledge graph",
        text: "A graph of data intended to accumulate and convey knowledge of the real world, whose nodes represent entities of interest and whose edges represent relations between them.",
        source: "Hogan et al., Knowledge Graphs, ACM Computing Surveys 54(4), 2021",
        url: "https://doi.org/10.1145/3447772",
      },
      { term: "RDF triple", text: "The unit of a knowledge graph: subject - predicate - object, for example elbow - has upper limit - 1.6 rad.", source: "W3C RDF 1.1 Concepts and Abstract Syntax", url: "https://www.w3.org/TR/rdf11-concepts/" },
      { term: "SHACL", text: "a language for validating RDF graphs against a set of conditions", quote: true, source: "W3C SHACL Recommendation, 2017", url: "https://www.w3.org/TR/shacl/" },
      {
        term: "CORA",
        text: "The Core Ontology for Robotics and Automation: general robotics concepts, their definitions, attributes, constraints and relations, as a base for specialised ontologies.",
        source: "IEEE 1872-2015, Standard Ontologies for Robotics and Automation",
        url: "https://standards.ieee.org/standard/1872-2015.html",
      },
    ],
    body: `The same elbow appears in the URDF, in the Modelica model, in a datasheet, in a test report. Each uses its own names and units. An **ontology** is an agreed vocabulary with rules - *a joint connects two links; a joint limit is an angle; an angle has a unit* - written so that a computer can check it.

A **knowledge graph** stores the facts using that vocabulary, as a network of small sentences (triples): *elbow* -is a→ *revolute joint*; *elbow* -has upper limit→ *1.6 rad*; that value -comes from→ *the URDF file at this commit*. The studio uses public standards rather than inventing its own words: **CORA** (IEEE 1872) for robotics, **QUDT** for quantities and units, **PROV-O** (W3C) for provenance, and **SHACL** rules to check the data. The graph lives in **GraphDB** on this computer and is queried with **SPARQL**.

**Why we propose it:**
1. **One meaning across tools** - the URDF, the Modelica model and the documentation are linked element by element.
2. **Mistakes caught by rules** - a limit in the wrong unit, a missing mass, a parameter outside its declared bounds are flagged automatically.
3. **Grounded AI** - the assistant answers from retrieved facts with sources, not from memory. Whether this measurably improves AI-assisted modelling is the research question the studio is built to test.`,
    visuals: ["ontology", "semantic-stack"],
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
    definitions: [
      {
        term: "Learning from demonstration",
        text: "Deriving a policy - a mapping from what the robot observes to what it does - from example executions of the task provided by a teacher.",
        source: "Argall et al., A survey of robot learning from demonstration, Robotics and Autonomous Systems 57(5), 2009",
        url: "https://doi.org/10.1016/j.robot.2008.10.024",
      },
      {
        term: "Policy",
        text: "a mapping from perceived states of the environment to actions to be taken when in those states",
        quote: true,
        source: "Sutton & Barto, Reinforcement Learning: An Introduction, 2nd ed., 2018",
        url: "http://incompleteideas.net/book/the-book-2nd.html",
      },
      {
        term: "ACT (Action Chunking with Transformers)",
        text: "An imitation-learning policy that predicts a whole sequence (a chunk) of future actions at once with a transformer, which shortens the effective decision horizon and reduces compounding errors.",
        source: "Zhao et al., Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware, RSS 2023",
        url: "https://arxiv.org/abs/2304.13705",
      },
    ],
    body: `ALOHA was designed for **teleoperation**: a person moves a small **leader** arm (here a WidowX 250) by hand, and the **follower** arm (the ViperX 300 S that does the work) mirrors it joint by joint. Every movement is recorded - joint angles, gripper, camera images.

Many recorded demonstrations of a task are then used to train a **policy**: a neural network that maps what the robot sees to what it should do next. ALOHA's original work introduced **ACT**, which predicts short sequences of actions at once. This is **imitation learning** - learning by watching, rather than by trial and error. **ALOHA 2** (2024) is the improved hardware this studio models.

What the studio does today: you record leader motions, replay them on the follower, and simulate the follower's response with its physics model. It **does not train a policy** - it focuses on the engineering model that a learned policy would ultimately run on.`,
    visuals: ["leader-follower", "lfd-pipeline", "chunking"],
    studio: [{ page: 0, label: "Robot & motion", what: "record a leader demonstration and replay it on the follower" }],
    related: ["sim2real", "kinematics", "trust", "foundation-models"],
  },
  {
    id: "trust",
    region: "learning",
    title: "AI you can trust",
    gist: "A language model may sound right while guessing. Grounding and human approval keep it honest.",
    definitions: [
      {
        term: "Hallucination",
        text: "generated content that is nonsensical or unfaithful to the provided source content",
        quote: true,
        source: "Ji et al., Survey of Hallucination in Natural Language Generation, ACM Computing Surveys, 2023",
        url: "https://arxiv.org/abs/2202.03629",
      },
      {
        term: "Retrieval-augmented generation (RAG)",
        text: "Language generation by models that combine pre-trained parametric and non-parametric memory: the model's own weights plus documents retrieved for each question.",
        source: "Lewis et al., NeurIPS 2020",
        url: "https://arxiv.org/abs/2005.11401",
      },
      {
        term: "Trustworthy AI",
        text: "AI that is valid and reliable; safe; secure and resilient; accountable and transparent; explainable and interpretable; privacy-enhanced; and fair, with harmful bias managed.",
        source: "NIST AI Risk Management Framework (AI RMF 1.0), 2023",
        url: "https://doi.org/10.6028/NIST.AI.100-1",
      },
    ],
    body: `Large language models are fluent - and that is the danger: a confident answer about a joint limit may be invented. In engineering, the cost of a plausible wrong number is high.

Three habits make AI useful here:
- **Grounding** - before answering, the assistant retrieves the relevant facts (from the knowledge graph and source files) and must cite them. When the retrieval walks a knowledge graph, this is often called **GraphRAG**. You can compare an answer *with* and *without* this evidence side by side.
- **Bounded tools** - the AI can read and propose, never change the model by itself. Proposed parameter changes are checked against declared bounds and limited to tunable settings, not manufacturer facts.
- **Human approval** - a proposal becomes a new model version only after a passing OpenModelica check and a person accepting it.

The model runs **locally** (NVIDIA Nemotron through Ollama): no robot data leaves the computer.`,
    visuals: ["grounding", "rag"],
    studio: [{ page: 2, label: "AI assistant", what: "the same question answered with and without the knowledge graph" }],
    related: ["ontology", "provenance"],
  },
  {
    id: "foundation-models",
    region: "learning",
    title: "Robot foundation models",
    gist: "One large AI model meant to drive many robots and tasks - but it still needs the robot's body described correctly.",
    definitions: [
      {
        term: "Vision-language-action model (VLA)",
        text: "A model that takes camera images and a language instruction and outputs robot actions, built by training a vision-language model so that actions are produced like another kind of token.",
        source: "Brohan et al., RT-2: Vision-Language-Action Models Transfer Web Knowledge to Robotic Control, 2023",
        url: "https://arxiv.org/abs/2307.15818",
        note: "The RT-2 paper introduced the name; later VLAs (OpenVLA, pi0, GR00T) produce actions in other ways but keep the name.",
      },
      {
        term: "World action model (WAM)",
        text: "a foundation model designed to predict both actions and visual future states in an aligned manner",
        quote: true,
        source: "Ye et al. (NVIDIA), World Action Models are Zero-shot Policies (DreamZero), 2026",
        url: "https://arxiv.org/abs/2602.15922",
        note: "A recent term (February 2026), used by NVIDIA's DreamZero and by Dream Labs' Dream-1; not yet a settled standard.",
      },
      {
        term: "Cross-embodiment",
        text: "Training one generalist policy on data from many different robots so that it can be adapted efficiently to new robots, tasks and environments.",
        source: "Open X-Embodiment Collaboration, Open X-Embodiment: Robotic Learning Datasets and RT-X Models, 2023",
        url: "https://arxiv.org/abs/2310.08864",
      },
      {
        term: "End-effector pose",
        text: "Where the gripper is and how it is turned (position and orientation of the end-effector frame), as opposed to the joint angles that put it there.",
        ...MR,
      },
    ],
    body: `Until recently, each robot learned each task separately: record demonstrations on *this* arm, train a policy for *this* task. **Robot foundation models** try the opposite: one large model, trained on many robots, many tasks, and lots of video, that you then point at a new robot.

Two families matter today. A **VLA** (vision-language-action model) looks at camera images, reads an instruction such as "fold the towel", and outputs the next moves. A **world action model** also *imagines what the camera will see next* and uses that picture of the future to choose its moves; it learns much of how the world moves from ordinary video. Examples as of October 2026: Physical Intelligence's pi models, NVIDIA GR00T, Google DeepMind's Gemini Robotics, and Dream Labs' Dream-1 (released 19 October 2026).

**The detail that matters for this studio: what the model outputs.**
- **Joint angles** - "shoulder to 0.4 rad, elbow to -0.2 rad...". Precise, but tied to one body: another arm with different link lengths needs different angles. ALOHA's own ACT policy works this way.
- **Gripper poses** - "left gripper here, turned like this, closed". The same instruction fits any two-armed robot, which is how Dream-1 drives robots it has never seen. But someone still has to turn the pose into joint angles (**inverse kinematics**), and Dream-1's own documentation says it controls only where the gripper ends up, not how the arm gets there.

So a gripper-pose model hands three questions to whoever integrates the robot: *Can this arm reach that pose within its joint limits? Will the motors manage the torque and speed? Do we trust the numbers in the robot's description?* Those are exactly the questions the studio's engineering model answers, offline and with every number traced to its source. The studio does not compete with these models; it is a check you can run **before** a policy's motions reach the real arm.

What we know and what is only claimed is tracked, with dates and links, in docs/FIELD_WATCH.md.`,
    visuals: ["fm-outputs"],
    studio: [
      { page: 0, label: "Robot & motion", what: "move the gripper and watch inverse kinematics pick joint angles within the limits" },
      { page: 5, label: "Joint simulation", what: "see whether a joint motion stays within the motor's torque" },
    ],
    related: ["demonstrations", "kinematics", "benchmarks"],
  },
  {
    id: "benchmarks",
    region: "learning",
    title: "Benchmarks: how robot AI is measured",
    gist: "A benchmark scores how often a robot's AI finishes a task. It does not say whether the robot's engineering model is right.",
    definitions: [
      {
        term: "Benchmark (robot manipulation)",
        text: "A fixed set of tasks, scenes and scoring rules on which different robot policies are run in the same way, so that their success rates can be compared.",
        source: "Liu et al., LIBERO: Benchmarking Knowledge Transfer for Lifelong Robot Learning, 2023",
        url: "https://arxiv.org/abs/2306.03310",
      },
      {
        term: "Success rate",
        text: "The share of attempts, out of a fixed number of evaluation episodes per task, in which the policy completes the task.",
        source: "Chen et al., RoboTwin 2.0, 2025 (protocol: 100 evaluation episodes per task)",
        url: "https://arxiv.org/abs/2506.18088",
      },
      {
        term: "Sim and real evaluation",
        text: "Running the same policies both in simulated tasks and on standardised physical robots, so that results in simulation can be compared with results in the real world.",
        source: "Chen et al., RoboDojo: A Unified Sim-and-Real Benchmark for Generalist Robot Manipulation Policies, 2026",
        url: "https://arxiv.org/abs/2607.04434",
      },
      {
        term: "Validation",
        text: "The process of determining the degree to which a model is an accurate representation of the real world from the perspective of the intended uses of the model.",
        quote: true,
        source: "U.S. DoD Instruction 5000.61; AIAA G-077-1998",
      },
    ],
    body: `When a company says its robot AI is "the best", the honest follow-up is: *measured how, and by whom?* A **benchmark** answers the first half. It fixes a list of tasks (stack the bowls, hand a cube from one arm to the other), runs every policy the same number of times, and counts **successes**.

The best-known ones for arms like ALOHA:
- **LIBERO** - simulated single-arm tasks. So many models now score above 90 % that researchers argue it mostly measures memorisation.
- **SimplerEnv** - simulated tasks designed so that the ranking matches real robots; single-arm only.
- **RoboTwin 2.0** - 50 two-arm tasks in simulation, including an ALOHA-style robot, with "easy" and deliberately messy "hard" scenes.
- **RoboDojo** (2026) - two-arm tasks in simulation **and** on real robots. Even the best AI succeeded on about 13 % of real tasks, against 100 % for people.
- **gym-aloha** - two simulated ALOHA tasks from the original ACT work.

**And by whom?** Most published numbers come from the people who built the model (a *vendor claim*). Independent evaluators are new: RoboDojo's authors and Robocurve, which scored Dream-1 at 59 % on its real-robot test in October 2026. Both kinds are worth reading; they are not worth the same.

**What a benchmark does not tell you:** whether the robot's own description is right (a joint limit in the wrong unit, a missing mass), whether a motion stays within the motors' torque, or where each number came from. A policy can score well and still be driven by a wrong robot model.

**Why the studio is not on these leaderboards:** it trains no policy, so there is nothing of its own to score. Its evidence is of a different kind:
1. **Twin validation** - compare what the engineering model predicts with what the real ALOHA arm did, on public recordings, keeping some recordings aside until the model is frozen. This is being set up; no validated result is claimed yet.
2. **Rule-check detection** - errors are planted on purpose in a copy of the model (a flipped axis, a limit in degrees); the experiment counts which checker finds them. The ontology rules found 12 of 16, all correctly typed, with no false alarms (results of 16 October 2026).
3. **The grounding question** - does giving the AI assistant facts from the knowledge graph make its modelling help measurably better? In that experiment, the small local model was not improved by the graph evidence; the question stays open.`,
    visuals: ["bench-vs-studio"],
    studio: [
      { page: 7, label: "Engineering reasoning", what: "the rules that catch planted errors, joint by joint" },
      { page: 0, label: "Robot & motion", what: "record and replay motions on the follower model" },
    ],
    related: ["foundation-models", "sim2real", "ontology"],
  },
  {
    id: "sim2real",
    region: "reality",
    title: "The sim-to-real gap - our challenge",
    gist: "A simulation is right only about what it models. The gap is everything else - and we have to measure it.",
    definitions: [
      {
        term: "Reality gap",
        text: "The difference between how a controller or policy behaves in simulation and how it behaves on the physical robot.",
        source: "Jakobi, Husbands & Harvey, ECAL 1995; Tobin et al., IROS 2017",
        url: "https://arxiv.org/abs/1703.06907",
      },
      { term: "System identification", text: "Building mathematical models of dynamical systems from measured input/output data.", source: "Ljung, System Identification: Theory for the User, 2nd ed., 1999" },
      {
        term: "Verification",
        text: "The process of determining that a model implementation accurately represents the developer's conceptual description and specification.",
        quote: true,
        source: "U.S. DoD Instruction 5000.61; AIAA G-077-1998",
      },
      {
        term: "Validation",
        text: "The process of determining the degree to which a model is an accurate representation of the real world from the perspective of the intended uses of the model.",
        quote: true,
        source: "U.S. DoD Instruction 5000.61; AIAA G-077-1998",
      },
      {
        term: "Domain randomisation",
        text: "Training across many randomly varied simulated conditions so that the real world looks like just one more variation.",
        source: "Tobin et al., IROS 2017",
        url: "https://arxiv.org/abs/1703.06907",
      },
    ],
    body: `A controller tuned in simulation, or a policy trained there, often behaves differently on the real robot. This **sim-to-real gap** comes from what the model leaves out or gets wrong:

- **Unmeasured parameters** - in this studio the servo gains and motor lag are *assumed*, and the URDF damping is a generic default, not identified on hardware.
- **Missing effects** - the joint model states what it does not include: motor rotor inertia through the gearbox, backlash, flexibility, payload, and how the two shoulder motors share the load.
- **Contact** - grasping and collisions are not modelled; the cube task is a visual scene, not physics.
- **Calibration** - where the arms stand relative to each other in the 3D scene is a display convention, not measured on the real cell.

Ways to close it: **system identification** (measure the real joint's response and fit the parameters), **validation** (compare recorded real motions with simulated ones), and for learned policies, **domain randomisation**. Note the two checks: *verification* asks "did we build the model right?", *validation* asks "did we build the right model?". The studio's OpenModelica checks are verification; validation needs the real robot. The precondition for all of them is what the studio already enforces: every parameter labelled *verified, derived or assumed*, so you know exactly what to measure next.

**This is our challenge:** turn the engineering model from a well-sourced estimate into a validated twin of the real ALOHA, one measured parameter at a time.`,
    visuals: ["sim2real", "close-gap", "vv"],
    studio: [
      { page: 5, label: "Joint simulation", what: "see which parameters are derived and which are assumed" },
      { page: 7, label: "Engineering reasoning", what: "assumptions listed explicitly, per joint" },
    ],
    related: ["provenance", "twin", "control", "demonstrations"],
  },
];

export const ROUTE = CONCEPTS.map((c) => c.id);
export const conceptById = (id?: string | null) => CONCEPTS.find((c) => c.id === id);

/** All definitions, alphabetical, with the concept they belong to (for the glossary view). */
export const GLOSSARY = CONCEPTS.flatMap((c) => c.definitions.map((d) => ({ ...d, concept: c.id }))).sort((a, b) => a.term.localeCompare(b.term));
