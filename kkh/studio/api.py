"""Persistent studio API, mounted before the static web application."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from .storage import Store, recover_audits
from . import robotics
from .models import Models

router=APIRouter(prefix="/api/workbench")
store=Store()
models=Models(store)
pool=ThreadPoolExecutor(max_workers=2)


@router.on_event("startup")
def recover_state():
    recover_audits(store)
    for record in store.list("job",limit=2000):
        if record["data"].get("status")=="running":
            store.update(record["id"],record["version"],{**record["data"],"status":"interrupted","error":"Application restarted; existing sources and messages were preserved."})
    for record in store.list("message",limit=2000):
        if record["data"].get("status")=="pending":
            store.update(record["id"],record["version"],{**record["data"],"status":"interrupted","error":"Application restarted during inference. Resubmit the question to retry."})


def job(name, fn):
    record=store.create("job",name,{"status":"running"})
    def work():
        try:
            result={"status":"complete","result":fn()}
        except Exception as exc:
            result={"status":"error","error":str(exc)}
        store.update(record["id"],record["version"],result)
    pool.submit(work)
    return record


def guard(fn):
    try:
        return fn()
    except KeyError as exc:
        raise HTTPException(404,str(exc)) from exc
    except (ValueError,TypeError) as exc:
        raise HTTPException(409,str(exc)) from exc


class Document(BaseModel):
    name:str=Field(default="Untitled",max_length=160)
    data:dict=Field(default_factory=dict)
    version:int=1


@router.get("/configuration")
def configuration():
    return robotics.description()


@router.get("/documents/{kind}")
def documents(kind:str,search:str=""):
    if kind not in {"trajectory","conversation","model","revision","simulation","session"}:
        raise HTTPException(404)
    return store.conversations(search) if kind=="conversation" else store.list(kind,search)


@router.post("/documents/{kind}")
def create(kind:str,body:Document):
    if kind=="model":
        return guard(lambda:models.create(body.name))
    if kind not in {"trajectory","conversation","session"}:
        raise HTTPException(422,"Unsupported record type")
    data=guard(lambda:robotics.trajectory(body.data)) if kind=="trajectory" else body.data
    if kind=="trajectory" and data.get("scenario"):
        from kkh import scenarios as S
        sc=guard(lambda:S.load(data["scenario"].get("id","")))
        if data["scenario"].get("version")!=sc["version"]:raise HTTPException(422,"Scenario version mismatch")
        data["scenario"]={"id":sc["id"],"version":sc["version"],"sha256":sc["sha256"],"file":sc["file"]}
    record=store.create(kind,body.name,data)
    if kind=="trajectory":
        from kkh.semantic.trace import record_observation
        record_observation(record)  # GraphDB engineering trace; best effort, never blocks saving
    return record


@router.get("/record/{identity}")
def record(identity:str):
    return guard(lambda:store.get(identity))


@router.patch("/record/{identity}")
def update(identity:str,body:Document):
    old=guard(lambda:store.get(identity))
    if old["kind"] not in {"conversation","trajectory","session","model"}:
        raise HTTPException(422,"Record is immutable")
    # Trajectory/model payloads cannot be overwritten through the generic metadata route.
    data=body.data if old["kind"]=="session" else old["data"]
    return guard(lambda:store.update(identity,body.version,data,body.name))


@router.delete("/record/{identity}")
def delete(identity:str,version:int,confirmed:bool=False):
    old=guard(lambda:store.get(identity))
    if not confirmed or old["kind"] not in {"trajectory","conversation"}:
        raise HTTPException(422,"Explicit confirmation is required for trajectory or conversation deletion")
    return guard(lambda:store.update(identity,version,delete=True))


class Pose(BaseModel):
    q:list[float]
    target:list[float]|None=None


@router.post("/pose")
def pose(body:Pose):
    def compute():
        mapped=robotics.mapping(body.q)
        return {"leader":robotics.poses(body.q),"follower":robotics.poses(mapped["q"],"aloha_vx300s"),"mapping":mapped}
    return guard(compute)


@router.post("/ik")
def ik(body:Pose):
    return guard(lambda:robotics.inverse_kinematics(body.q,body.target))


@router.post("/follower-pose")
def follower_pose(body:Pose):
    # Dynamic response may exceed command limits; show measured coordinates without clamping them.
    import numpy as np
    from scipy.spatial.transform import Rotation
    q=np.asarray(body.q,dtype=float)
    if q.shape!=(8,) or not np.all(np.isfinite(q)):raise HTTPException(422,"Expected eight finite measured coordinates")
    transforms=robotics.robot_for("aloha_vx300s").forward_kinematics(dict(zip(robotics.JOINTS,q)))
    return {name:[*T[:3,3].tolist(),*Rotation.from_matrix(T[:3,:3]).as_quat().tolist()] for name,T in transforms.items()}


@router.post("/trajectory/{identity}/smooth")
def smooth(identity:str,window:int=9):
    old=guard(lambda:store.get(identity,"trajectory"))
    data=guard(lambda:robotics.smooth(old["data"],window))
    return store.create("trajectory",old["name"]+" · smoothed",{**data,"parent":identity})


class Control(BaseModel):
    model:str|None=None
    candidate_revision:str|None=None
    reference_revision:str|None=None
    focus:str="shoulder"


@router.post("/trajectory/{identity}/simulate")
def dynamics(identity:str,body:Control,axes:int=6):
    """Simulate the recorded reference on the model's reference revision and (if different) its candidate revision.

    Servo gains/lag/feed-forward are read from each revision's Control/FollowerServoSettings.mo. Defaults:
    reference = accepted revision, else the model's initial revision; candidate = current head."""
    old=guard(lambda:store.get(identity,"trajectory"))
    if axes not in {1,6}: raise HTTPException(422,"Use 1 or 6 dynamic axes")
    from .models import BASELINE
    from .robotics import JOINTS
    if body.focus not in JOINTS[:6]: raise HTTPException(422,"Focus must be one of the six arm joints")
    runs=[{"name":"reference","package":BASELINE,"revision":None,"label":"generated baseline"}]
    if body.model:
        workspace=guard(lambda:store.get(body.model,"model"))
        if guard(lambda:models.changes(body.model))["changes"]:raise HTTPException(409,"Import or reject external model changes first")
        revisions=guard(lambda:models.revisions(body.model))
        reference=body.reference_revision or workspace["data"].get("accepted") or revisions[-1]["id"]
        candidate=body.candidate_revision or workspace["data"]["head"]
        def described(rid,name):
            rev=guard(lambda:store.get(rid,"revision"))
            if rev["data"]["workspace"]!=body.model:raise HTTPException(422,"Revision belongs to another model")
            return {"name":name,"package":models.revision_dir(rev),"revision":rid,
                    "label":f"{rev['data']['status']} · {rev['name'][:60]}","status":rev["data"]["status"]}
        runs=[described(reference,"reference")]
        if candidate!=reference:runs.append(described(candidate,"candidate"))
    def run():
        from .dynamics import compare
        result=compare(old["data"],axes,runs,body.focus)
        labels=" vs ".join(r["label"].split(" · ")[0] for r in runs)
        record=store.create("simulation",old["name"]+f" · {body.focus} · {labels}",
                            {**result,"trajectory":identity,"model":body.model,
                             "model_revision":runs[-1]["revision"],"reference_revision":runs[0]["revision"]})
        from kkh.semantic.trace import record_simulation
        revs={r["revision"]:store.get(r["revision"],"revision") for r in runs if r.get("revision")}
        trace=record_simulation(record,revs)
        return store.update(record["id"],record["version"],{**record["data"],"trace":trace})
    return job("Follower revision comparison",run)


@router.get("/conversation/{identity}")
def conversation(identity:str):
    guard(lambda:store.get(identity,"conversation"))
    return store.messages(identity)


@router.get("/conversation/{identity}/export")
def export(identity:str,format:str="json"):
    record=guard(lambda:store.get(identity,"conversation")); messages=conversation(identity)
    if format=="json":
        text=json.dumps({"conversation":record,"messages":messages},indent=2); media="application/json"
    elif format=="md":
        text="# "+record["name"]+"\n\n"+"\n\n".join("## "+m["data"].get("mode",m["data"]["role"])+" · "+m["created"]+"\n\n"+str(m["data"].get("content") or m["data"].get("error",""))+"\n\nContext: `"+json.dumps(m["data"].get("context",{}))+"`" for m in messages);media="text/markdown"
    else:raise HTTPException(422,"Use json or md")
    return Response(text,media_type=media,headers={"Content-Disposition":f'attachment; filename="conversation-{identity}.{format}"'})


class Question(BaseModel):
    question:str=Field(min_length=3,max_length=1500)
    model:str="qwen3:4b"
    context:dict=Field(default_factory=dict)


@router.post("/conversation/{identity}/ask")
def ask(identity:str,body:Question):
    guard(lambda:store.get(identity,"conversation"))
    from .copilot import pair
    return job("Dual local copilot",lambda:pair(store,identity,body.question,body.model,body.context))


@router.get("/job/{identity}")
def get_job(identity:str):
    return guard(lambda:store.get(identity,"job"))


@router.get("/model/{identity}/files")
def files(identity:str):
    return guard(lambda:models.files(identity))


@router.get("/model/{identity}/source")
def source(identity:str,path:str,compare_revision:str|None=None):
    return guard(lambda:models.source(identity,path,compare_revision))


class Source(BaseModel):
    path:str
    source:str
    expected_hash:str
    proposal:bool=False


@router.put("/model/{identity}/source")
def save(identity:str,body:Source):
    return guard(lambda:models.save(identity,body.path,body.source,body.expected_hash,status="AI proposal" if body.proposal else "working"))


@router.get("/model/{identity}/changes")
def changes(identity:str):
    return guard(lambda:models.changes(identity))


class Action(BaseModel):
    action:str
    path:str="package.mo"
    hashes:dict=Field(default_factory=dict)
    revision:str=""
    class_name:str="ALOHA2.Experiments.RightArmReach"
    stop_time:float=Field(default=9,ge=.1,le=120)


@router.post("/model/{identity}/action")
def action(identity:str,body:Action):
    if body.action=="open":return guard(lambda:models.open_native(identity,body.path))
    if body.action=="ensure_control":return {"revision":guard(lambda:models.ensure_control(identity))}
    if body.action in {"import","reject"}:return guard(lambda:models.roundtrip(identity,body.action,body.hashes))
    if body.action=="accept":
        accepted=guard(lambda:models.accept(identity,body.revision))
        from kkh.semantic.trace import record_acceptance
        record_acceptance(identity,store.get(body.revision,"revision"))
        return accepted
    if body.action=="restore":return guard(lambda:models.restore(identity,body.revision,body.hashes))
    if body.action in {"check","simulate"}:
        def validate():
            head=store.get(identity,"model")["data"]["head"]
            result=models.validate(identity,body.class_name,body.action=="simulate",body.stop_time)
            from kkh.semantic.trace import record_validation
            revision=store.get(head,"revision")
            record_validation(revision,revision["data"].get("status")=="validated",body.class_name)
            return result
        return job("OpenModelica "+body.action,validate)
    raise HTTPException(422,"Unknown action")


class Proposal(BaseModel):
    message:str
    indices:list[int]=Field(default_factory=list)


@router.post("/model/{identity}/propose")
def propose(identity:str,body:Proposal):
    """Turn structurally valid parameter changes from a STORED copilot answer into an 'AI proposal' revision.

    Changes are read from the stored message, never from the browser payload. Nothing is accepted automatically:
    the revision must be reviewed, validated by OpenModelica and explicitly accepted in the Modelica editor."""
    msg=guard(lambda:store.get(body.message,"message"))
    changes=[c for i,c in enumerate(msg["data"].get("parameter_changes") or []) if not body.indices or i in body.indices]
    # Re-decide applicability now from the knowledge graph (stored answers are never trusted for this decision).
    from .copilot import ontology_applicability
    valid,rejected,decisions=[],[],{}
    for c in changes:
        if not c.get("structurally_valid") or not c.get("file"):continue
        path_=f"ALOHA2.{c['file'][:-3].replace('/','.')}.{c['component']}"
        d=ontology_applicability(path_,c["parameter"],c["file"])
        if d["applicable"]:
            valid.append({k:c.get(k) for k in ("component","parameter","value","file")})
            decisions[(c["component"],c["parameter"])]={**d,"justification":c.get("justification")}
        else:
            rejected.append(f"{c['component']}.{c['parameter']}: {d['reason']}")
    if not valid:raise HTTPException(422,"No applicable parameter change selected"+("; rejected: "+"; ".join(rejected) if rejected else ""))
    path=(msg["data"].get("context") or {}).get("file","Arms/AlohaVX300s.mo")
    reason=(f"AI proposal from copilot ({msg['data'].get('mode')} ontology, {msg['data'].get('settings',{}).get('model')}, "
            f"message {msg['id'][:8]}): "+", ".join(f"{c['component']}.{c['parameter']}={c['value']}" for c in valid))
    result=guard(lambda:models.propose_parameters(identity,path,valid,reason))
    for a in result["applied"]:
        d=decisions.get((a["component"],a["parameter"]),{})
        a.update({"parameter_iri":d.get("iri"),"justification":d.get("justification"),"semantic_basis":d.get("basis"),
                  "evidence_status":d.get("evidence_status")})
    from kkh.semantic.trace import record_proposal
    result["trace"]=record_proposal(msg,result["applied"],store.get(result["revision"],"revision"),identity)
    result["rejected"]=rejected
    store.update(msg["id"],msg["version"],{**msg["data"],"proposal_revision":result["revision"],"proposal_model":identity})
    return result


@router.get("/entity")
def entity(robot:str="aloha_vx300s",joint:str|None=None,file:str|None=None,component:str|None=None):
    """Resolve one engineering entity across representations using the generator's URDF<->Modelica mapping
    (generated/modelica/aloha2_mapping.json) and the evidence-graph IRIs. Either (robot, joint) or (file, component)."""
    from kkh.domain.aloha import configuration as C
    from kkh.domain.aloha.build import SERVO_JOINTS
    from kkh.domain.aloha.knowledge import entity as iri
    mapping=json.loads((C.ROOT/"generated/modelica/aloha2_mapping.json").read_text(encoding="utf-8"))["classes"]
    if file and component:
        if file.startswith("Control/") and component in SERVO_JOINTS:
            robot,joint="aloha_vx300s",component
        else:
            robot=next((m for m,cls in C.ARM_CLASS.items() if file==f"Arms/{cls}.mo"),None)
            if robot is None:raise HTTPException(404,"No engineering entity mapped for this file")
            joint=next((j for j,c in mapping[robot]["joints"].items() if c==component),None)
            if joint is None:
                link=next((l for l,c in mapping[robot]["links"].items() if c==component),None)
                if link is None:raise HTTPException(404,"Component is not mapped to a URDF joint or link")
                joint=next((j.name for j in C.arm_robot(robot).joints.values() if j.child==link),None)
                if joint is None:raise HTTPException(404,"Root link has no parent joint")
    if robot not in C.ARM_CLASS:raise HTTPException(422,"Unknown robot")
    urdf=C.arm_robot(robot)
    if joint not in urdf.joints:raise HTTPException(404,"Unknown joint for this robot")
    j=urdf.joints[joint]; cls=mapping[robot]
    arm="leader" if robot=="aloha_wx250s" else "follower_right"
    record={"robot":robot,"joint":joint,"type":j.type,"iri":str(iri(f"{arm}/joint/{joint}")),
            "graph_arm":arm,
            "urdf":{"file":f"data/urdf/{robot}.urdf","joint":joint,"parent":j.parent,"child":j.child,
                    "axis":j.axis.tolist() if j.movable else None},
            "modelica":{"file":f"Arms/{C.ARM_CLASS[robot]}.mo","class":cls["class"],"component":cls["joints"][joint],
                        "parent_component":cls["links"][j.parent],"child_component":cls["links"][j.child]},
            "servo":({"file":"Control/FollowerServoSettings.mo","component":joint,"class":"ALOHA2.Control.FollowerServoSettings"}
                     if robot=="aloha_vx300s" and joint in SERVO_JOINTS else None),
            "actuators":C.ACTUATORS[robot].get(joint),"servo_ids":C.SERVO_IDS.get(joint) if joint in C.ACTUATORS[robot] else None,
            "metrics_index":C.ACTUATED.index(joint) if joint in C.ACTUATED[:6] else None,
            "mapping_source":"generated/modelica/aloha2_mapping.json"}
    return record


# ---------------------------------------------------------------------------------------------- task scenarios
@router.get("/scenarios")
def scenarios_list():
    from kkh import scenarios as S
    return S.available()


@router.get("/scenarios/{scenario_id}")
def scenario(scenario_id:str):
    from kkh import scenarios as S
    return guard(lambda:S.load(scenario_id))


@router.post("/follower-ik")
def follower_ik(body:Pose):
    """Cartesian control: place the FOLLOWER end effector (follower base frame); returns a leader joint command."""
    from kkh.domain.aloha.scenario_binding import follower_ik as solve
    if body.target is None:raise HTTPException(422,"target required")
    return guard(lambda:solve(body.q,body.target))


@router.get("/trajectory/{identity}/task")
def task_result(identity:str):
    """Level-1 visual task evaluation of a saved recording (deterministic backend computation)."""
    from kkh import scenarios as S
    record=guard(lambda:store.get(identity,"trajectory"))
    info=record["data"].get("scenario")
    if not info:raise HTTPException(404,"This recording is not linked to a task scenario")
    def compute():
        sc=S.load(info["id"])
        ee,opening=S.binding(sc).signals(record["data"]["q"])
        result=S.evaluate(sc,record["data"]["time"],ee,opening)
        result["scenario_version_recorded"]=info.get("version")
        result["scenario_changed_since_recording"]=info.get("sha256") not in (None,sc["sha256"])
        return result
    return guard(compute)


# ---------------------------------------------------------------------------------------------- semantic engineering
@router.get("/semantic/joint")
def semantic_joint(robot:str="aloha_vx300s",joint:str="shoulder"):
    """Ontology chain (actuators, servo controller, parameters, Modelica bindings, evidence) and engineering trace."""
    from kkh.semantic.graphdb import GraphDB
    from kkh.semantic.trace import joint_chain, joint_trace
    from kkh.studio.robotics import JOINTS
    if joint not in JOINTS:raise HTTPException(422,"Unknown joint")
    arm="leader" if robot=="aloha_wx250s" else "follower_right"
    db=GraphDB(timeout=10)
    try:
        return {"chain":guard(lambda:joint_chain(db,arm,joint)),
                "trace":guard(lambda:joint_trace(db,joint)) if arm!="leader" else None,
                "graphs":{"evidence":"https://w3id.org/kkh/graphs/aloha2","trace":"https://w3id.org/kkh/graphs/aloha2/trace"}}
    finally:
        db.close()


@router.post("/semantic/backfill")
def semantic_backfill():
    """Record existing recordings, simulations, proposals and acceptances in the GraphDB engineering trace (idempotent)."""
    from kkh.semantic.trace import backfill
    return guard(lambda:backfill(store))
