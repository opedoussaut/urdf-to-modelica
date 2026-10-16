"""Behavioral regressions: preservation, durable state, mapping/IK and paired isolation."""
import json
from pathlib import Path
import numpy as np
import pytest
from kkh.studio.storage import Store
from kkh.studio.models import Models, manifest
from kkh.studio import robotics as R


def recording():
    t=np.linspace(0,2,21);q=np.tile(R.C.start_vector(),(21,1));q[:,0]=.1*t**2
    return R.trajectory({"configuration_id":R.CONFIG_ID,"joint_ids":R.JOINTS,"time":t.tolist(),"q":q.tolist()})


def test_sqlite_restart_conflict_and_history(tmp_path):
    path=tmp_path/'studio.sqlite';store=Store(path)
    chat=store.create('conversation','Persistent engineering',{'context':{'selected':'elbow'}})
    saved=store.create('message','user',{'conversation':chat['id'],'role':'user','content':'Actual question'})
    renamed=store.update(chat['id'],1,name='Renamed')
    reopened=Store(path)
    assert reopened.get(saved['id'])['data']['content']=='Actual question'
    assert reopened.conversations('Actual question')[0]['id']==chat['id']
    assert reopened.messages(chat['id'])[0]['id']==saved['id']
    assert reopened.list('conversation','Renamed')[0]['version']==2
    with pytest.raises(ValueError):reopened.update(chat['id'],1,name='Lost update')
    assert reopened.history(chat['id'])[0]['name']=='Persistent engineering'
    reopened.update(chat['id'],renamed['version'],delete=True)
    with pytest.raises(KeyError):reopened.get(chat['id'])
    assert reopened.history(chat['id'])[0]['name']=='Renamed'


def test_trajectory_identity_derivatives_and_smoothing():
    data=recording()
    assert np.allclose(np.array(data['qd'])[:,0],.2*np.array(data['time']),atol=1e-12)
    assert np.allclose(np.array(data['qdd'])[:,0],.2,atol=1e-12)
    before=json.dumps(data);smooth=R.smooth(data,9)
    assert json.dumps(data)==before and smooth['derived']
    assert smooth['configuration_id']==R.CONFIG_ID and smooth['units'][-1]=='m'
    with pytest.raises(ValueError):R.trajectory({**data,'configuration_id':'other'})
    with pytest.raises(ValueError):R.trajectory({**data,'time':[0]*21})


def test_mapping_limits_mimic_and_unreachable():
    q=R.C.start_vector();original=list(q);q[1]=1.8
    mapped=R.mapping(q)
    assert mapped['warnings'] and mapped['q'][1]<=R.robot_for('aloha_vx300s').joints['shoulder'].limit.upper
    assert mapped['mode']=='kinematic replay'
    poses=R.poses(original)
    assert R.inverse_kinematics(original,poses['ee_gripper_link'][:3])['success']
    result=R.inverse_kinematics(original,[50,50,50])
    assert not result['success'] and result['q']==original
    R.mapping(original)
    assert original==R.C.start_vector()


def test_native_roundtrip_and_baseline_guard(tmp_path):
    baseline=tmp_path/'baseline';baseline.mkdir()
    (baseline/'package.mo').write_text('within; package ALOHA2 end ALOHA2;')
    (baseline/'Example.mo').write_text('within ALOHA2;\nmodel Example\n  Real x;\nequation\n  x=1;\nend Example;')
    before=manifest(baseline);store=Store(tmp_path/'state.sqlite');models=Models(store,tmp_path/'models',baseline)
    workspace=models.create();identity=workspace['id'];file=models.directory(identity)/'Example.mo'
    snapshot=models.source(identity,'Example.mo')
    file.write_text(snapshot['source'].replace('x=1','x=2'))
    with pytest.raises(ValueError):models.save(identity,'Example.mo','overwrite',snapshot['hash'])
    changes=models.changes(identity)
    assert len(changes['changes'])==1 and '+  x=2;' in changes['changes'][0]['diff']
    imported=models.roundtrip(identity,'import',changes['hashes'])
    assert imported['data']['head']!=workspace['data']['head']
    assert models.changes(identity)['changes']==[]
    file.write_text(file.read_text().replace('x=2','x=3'))
    changes=models.changes(identity);models.roundtrip(identity,'reject',changes['hashes'])
    assert 'x=2' in file.read_text()
    with pytest.raises(ValueError):models.accept(identity,imported['data']['head'])
    with pytest.raises(ValueError):models.source(identity,'../../baseline/Example.mo')
    assert manifest(baseline)==before


def test_dual_context_isolation_and_durable_errors(tmp_path,monkeypatch):
    from kkh.studio import copilot
    import kkh.rag.retrieval as retrieval
    import kkh.semantic.graphdb as graphdb
    store=Store(tmp_path/'state.sqlite');chat=store.create('conversation','Dual',{})
    calls=[]
    class Local:
        def __init__(self,**kw):pass
        def chat(self,messages,**settings):
            calls.append((messages,settings));return {'content':json.dumps({'answer':'Source-backed answer','source_paths':[],'assumptions':[],'proposed_change':''}),'metrics':{}}
        def close(self):pass
    class DB:
        def __init__(self,**kw):pass
        def close(self):pass
    monkeypatch.setattr(copilot,'Ollama',Local);monkeypatch.setattr(graphdb,'GraphDB',DB)
    retrieved=[]
    def retrieve(question,db):retrieved.append(question);return [{'id':'E1','property':'axis','value':'0,1,0'}]
    monkeypatch.setattr(retrieval,'retrieve',retrieve)
    paired=copilot.pair(store,chat['id'],'Explain elbow','local-test',{'selected':'elbow'})
    assert len(retrieved)==1 and len(calls)==2
    plain,grounded=sorted(calls,key=lambda v:'ADDITIONAL ONTOLOGY EVIDENCE' in v[0][-1]['content'])
    assert plain[0][0]==grounded[0][0] and plain[1]==grounded[1]
    assert 'ADDITIONAL ONTOLOGY EVIDENCE' not in plain[0][-1]['content']
    assert 'ADDITIONAL ONTOLOGY EVIDENCE' in grounded[0][-1]['content']
    plain_message=next(m for m in paired['messages'] if m['data']['mode']=='without')
    assert all('GraphDB' not in t['tool'] for t in plain_message['data']['trace'])
    assert len(Store(store.path).list('message'))==3
    def failure(*a,**kw):raise RuntimeError('GraphDB offline')
    monkeypatch.setattr(retrieval,'retrieve',failure)
    paired=copilot.pair(store,chat['id'],'Another elbow question','local-test',{})
    assert {m['data']['mode']:m['data']['status'] for m in paired['messages']}=={'without':'complete','with':'error'}
    paired=copilot.pair(store,chat['id'],'Keep this question despite invalid context','local-test',{'robot':'missing'})
    assert all(m['data']['status']=='error' for m in paired['messages'])
    assert any(m['data'].get('content')=='Keep this question despite invalid context' for m in Store(store.path).messages(chat['id']))


def test_tracking_metrics_do_not_claim_delay_for_unexcited_axes():
    from kkh.studio.dynamics import measure
    t=np.linspace(0,2,101);q=np.tile(R.C.start_vector(),(101,1));q[:,0]=.1*np.sin(t)
    class Result:
        time=t
        def get(self,name):
            prefix,index=name.split('[');index=int(index[:-1])-1
            if prefix=='q_reference':return q[:,index]
            if prefix=='q_actual':return q[:,index]+(.002 if index==0 else 0)
            if prefix=='tau_actual':return np.ones(len(t))*.5
            if prefix=='ee_reference':return np.zeros(len(t))
            if prefix=='ee_actual':return np.ones(len(t))*(.003 if index==0 else 0)
    metrics=measure(Result(),1)['metrics']
    assert metrics['joint_rms_rad'][0]==pytest.approx(.002)
    assert metrics['ee_rms_m']==pytest.approx(.003)
    assert metrics['delay_s'][1:]==[None]*5
    assert metrics['limit_violation_samples']==0


def test_package_order_and_matrix_placement_roundtrip(tmp_path):
    baseline=tmp_path/'baseline';baseline.mkdir()
    (baseline/'package.mo').write_text('within; package ALOHA2 end ALOHA2;')
    (baseline/'package.order').write_text('Example\n')
    (baseline/'Example.mo').write_text('within ALOHA2;\nmodel Example\n  Test body(I=[1,0;0,1]) annotation (Placement(transformation(origin={20,-40})));\nend Example;')
    models=Models(Store(tmp_path/'state.sqlite'),tmp_path/'models',baseline);w=models.create()
    source=models.source(w['id'],'Example.mo')
    assert source['components'][0]['position']==[20,-40]
    order=models.directory(w['id'])/'package.order';order.write_text('Example\nAdded\n')
    changes=models.changes(w['id']);assert changes['changes'][0]['path']=='package.order'
    models.roundtrip(w['id'],'reject',changes['hashes'])
    assert order.read_text()=='Example\n'


def test_persistent_api_search_export_and_delete_confirmation(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from kkh.api.main import app
    import kkh.studio.api as api
    state=Store(tmp_path/'api.sqlite');monkeypatch.setattr(api,'store',state)
    client=TestClient(app)
    conversation=client.post('/api/workbench/documents/conversation',json={'name':'API persistence','data':{'context':{'selected':'elbow'}}}).json()
    state.create('message','user',{'conversation':conversation['id'],'role':'user','content':'Needle in saved message','context':{'trajectory':'reference-id'}})
    found=client.get('/api/workbench/documents/conversation?search=Needle').json()
    assert found[0]['id']==conversation['id']
    assert client.get('/api/workbench/conversation/'+conversation['id']).json()[0]['data']['content']=='Needle in saved message'
    markdown=client.get('/api/workbench/conversation/'+conversation['id']+'/export?format=md')
    assert markdown.status_code==200 and 'Needle in saved message' in markdown.text and 'reference-id' in markdown.text
    exported=client.get('/api/workbench/conversation/'+conversation['id']+'/export?format=json').json()
    assert exported['conversation']['data']['context']['selected']=='elbow'
    assert client.delete('/api/workbench/record/'+conversation['id']+'?version=1').status_code==422
    assert client.delete('/api/workbench/record/'+conversation['id']+'?version=1&confirmed=true').status_code==200
    assert client.get('/api/workbench/conversation/'+conversation['id']).status_code==404


def test_recovery_does_not_resurrect_deleted_audit_history(tmp_path,monkeypatch):
    import kkh.studio.storage as storage
    audits=tmp_path/'runs/copilot';audits.mkdir(parents=True)
    (audits/'real-audit.json').write_text(json.dumps({'question':'Real old question','answer':'Real old answer'}))
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    store=Store(tmp_path/'state.sqlite');storage.recover_audits(store)
    conversation=store.get('recovered-real-audit');store.update(conversation['id'],conversation['version'],delete=True)
    storage.recover_audits(Store(store.path))
    assert store.conversations()==[]
    assert store.messages(conversation['id'])[0]['data']['content']=='Real old question'


def test_copilot_focus_follows_explicit_question():
    from kkh.studio.copilot import resolve_focus
    ui = {"robot": "aloha_wx250s", "selected": "shoulder"}
    r, n = resolve_focus("Which links does the follower elbow joint connect?", ui)
    assert (r["robot"], r["selected"]) == ("aloha_vx300s", "elbow")
    assert n["robot"]["from"] == "question" and n["joint"]["from"] == "question"
    r, _ = resolve_focus("Compare the leader and follower elbow", ui)       # ambiguous robot -> UI selection
    assert (r["robot"], r["selected"]) == ("aloha_wx250s", "elbow")
    r, _ = resolve_focus("Explain this joint", ui)                           # nothing named -> UI selection
    assert r == ui
