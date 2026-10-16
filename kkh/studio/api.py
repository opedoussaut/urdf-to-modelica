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
    return store.create(kind,body.name,data)


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
    kp:float=Field(default=80,ge=1,le=500)
    kd:float=Field(default=8,ge=0,le=80)
    lag:float=Field(default=.03,ge=.005,le=.3)
    model:str|None=None


@router.post("/trajectory/{identity}/simulate")
def dynamics(identity:str,body:Control,axes:int=6):
    old=guard(lambda:store.get(identity,"trajectory"))
    if axes not in {1,6}: raise HTTPException(422,"Use 1 or 6 dynamic axes")
    from .models import BASELINE
    source_package=BASELINE
    revision_id=None
    if body.model:
        workspace=guard(lambda:store.get(body.model,"model"))
        if guard(lambda:models.changes(body.model))["changes"]:raise HTTPException(409,"Import or reject external model changes first")
        revision_id=workspace["data"]["head"]
        revision=store.get(revision_id,"revision")
        source_package=models.revision_dir(revision)
    options=body.model_dump(exclude={"model"})
    settings=store.create("controller","Illustrative follower configuration",{"options":options,"model_revision":revision_id})
    def run():
        from .dynamics import compare
        result=compare(old["data"],axes,source_package,options)
        return store.create("simulation",old["name"]+f" · {axes} dynamic axes",{**result,"trajectory":identity,"model_revision":revision_id,"controller_revision":settings["id"]})
    return job("Follower control comparison",run)


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
    if body.action in {"import","reject"}:return guard(lambda:models.roundtrip(identity,body.action,body.hashes))
    if body.action=="accept":return guard(lambda:models.accept(identity,body.revision))
    if body.action=="restore":return guard(lambda:models.restore(identity,body.revision,body.hashes))
    if body.action in {"check","simulate"}:return job("OpenModelica "+body.action,lambda:models.validate(identity,body.class_name,body.action=="simulate",body.stop_time))
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
    valid=[{k:c[k] for k in ("component","parameter","value")} for c in changes if c.get("structurally_valid")]
    if not valid:raise HTTPException(422,"The answer contains no structurally valid parameter change")
    path=(msg["data"].get("context") or {}).get("file","Arms/AlohaVX300s.mo")
    reason=(f"AI proposal from copilot ({msg['data'].get('mode')} ontology, {msg['data'].get('settings',{}).get('model')}, "
            f"message {msg['id'][:8]}): "+", ".join(f"{c['component']}.{c['parameter']}={c['value']}" for c in valid))
    result=guard(lambda:models.propose_parameters(identity,path,valid,reason))
    store.update(msg["id"],msg["version"],{**msg["data"],"proposal_revision":result["revision"],"proposal_model":identity})
    return result
