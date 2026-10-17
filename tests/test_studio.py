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


def test_omedit_launch_loads_only_root_package(tmp_path,monkeypatch):
    import kkh.studio.models as module
    baseline=tmp_path/'baseline';(baseline/'Arms').mkdir(parents=True)
    (baseline/'package.mo').write_text('within; package ALOHA2 end ALOHA2;')
    (baseline/'Arms/Example.mo').write_text('within ALOHA2.Arms; model Example end Example;')
    installation=tmp_path/'omhome';(installation/'bin').mkdir(parents=True)
    (installation/'bin/OMEdit.exe').touch()
    monkeypatch.setattr(module,'DEFAULT_OMHOME',str(installation))
    calls=[];monkeypatch.setattr(module.subprocess,'Popen',lambda args,**kw:calls.append((args,kw)))
    models=Models(Store(tmp_path/'state.sqlite'),tmp_path/'models',baseline);w=models.create()
    result=models.open_native(w['id'],'Arms/Example.mo')
    assert calls[0][0]==[str(installation/'bin/OMEdit.exe'),str(models.directory(w['id'])/'package.mo')]
    assert result['selected_class']=='ALOHA2.Arms.Example'
    assert result['baseline_protected'] and 'Arms/Example.mo' in result['opened'].replace('\\','/')


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


def test_ai_parameter_proposal_becomes_unaccepted_revision(tmp_path):
    import shutil
    from kkh.studio.models import BASELINE
    baseline = tmp_path / 'baseline'
    shutil.copytree(BASELINE, baseline, ignore=shutil.ignore_patterns('*.stl'))
    before = manifest(baseline)
    models = Models(Store(tmp_path / 'state.sqlite'), tmp_path / 'models', baseline)
    w = models.create()
    head = w['data']['head']
    out = models.propose_parameters(w['id'], 'Arms/AlohaVX300s.mo',
                                    [{'component': 'j_shoulder', 'parameter': 'q_max', 'value': 1.2}], 'test proposal')
    assert out['applied'] == [{'file': 'Arms/AlohaVX300s.mo', 'component': 'j_shoulder', 'parameter': 'q_max',
                               'before': 1.256637061436, 'after': 1.2, 'bounds': None}]
    rev = models.store.get(out['revision'], 'revision')
    assert rev['data']['status'] == 'AI proposal' and rev['data']['parent'] == head
    text = (models.directory(w['id']) / 'Arms/AlohaVX300s.mo').read_text()
    assert 'q_max = 1.2,' in text and text.count('q_max = 1.2,') == 1
    assert models.store.get(w['id'], 'model')['data']['accepted'] is None          # never auto-accepted
    with pytest.raises(ValueError):
        models.accept(w['id'], out['revision'])                                      # not validated -> refused
    with pytest.raises(ValueError):
        models.propose_parameters(w['id'], 'Arms/AlohaVX300s.mo',
                                  [{'component': 'j_shoulder', 'parameter': 'n', 'value': 1.0}], 'vector rejected')
    assert manifest(baseline) == before                                              # baseline untouched


def test_servo_proposal_bounds_and_control_injection(tmp_path):
    import shutil
    from kkh.studio.models import BASELINE
    baseline = tmp_path / 'baseline'
    shutil.copytree(BASELINE, baseline, ignore=shutil.ignore_patterns('*.stl', 'Control'))   # model predating Control
    order = (baseline / 'package.order').read_text().split()
    (baseline / 'package.order').write_text('\n'.join(x for x in order if x != 'Control') + '\n')
    models = Models(Store(tmp_path / 'state.sqlite'), tmp_path / 'models', baseline)
    w = models.create()
    with pytest.raises(ValueError, match=r'outside the bounds declared in Modelica \[1, 500\]'):
        models.propose_parameters(w['id'], 'Arms/AlohaVX300s.mo',
                                  [{'file': 'Control/FollowerServoSettings.mo', 'component': 'shoulder', 'parameter': 'kp', 'value': 900.0}], 'too high')
    revs = models.revisions(w['id'])
    assert revs[0]['name'].startswith('Added Control package')           # injected as its own recorded revision
    out = models.propose_parameters(w['id'], 'Arms/AlohaVX300s.mo',
                                    [{'file': 'Control/FollowerServoSettings.mo', 'component': 'shoulder', 'parameter': 'kp', 'value': 120.0},
                                     {'component': 'j_shoulder', 'parameter': 'q_max', 'value': 1.5}], 'two files')
    assert {a['file'] for a in out['applied']} == {'Control/FollowerServoSettings.mo', 'Arms/AlohaVX300s.mo'}
    assert out['applied'][0]['bounds'] == [1.0, 500.0]
    from kkh.studio.dynamics import read_servo
    assert read_servo(models.directory(w['id']))['shoulder']['kp'] == 120.0


def test_copilot_proposal_checks_reject_noop_bounds_and_class_names():
    from kkh.studio.copilot import check_parameter_changes
    from kkh.studio.models import BASELINE
    src = [{"path": "generated/modelica/ALOHA2/Control/FollowerServoSettings.mo",
            "source": (BASELINE / "Control/FollowerServoSettings.mo").read_text()},
           {"path": "generated/modelica/ALOHA2/Arms/AlohaVX300s.mo",
            "source": (BASELINE / "Arms/AlohaVX300s.mo").read_text()}]
    out = check_parameter_changes([
        {"component": "shoulder", "parameter": "kp", "value": 120.0, "justification": "x"},
        {"component": "shoulder", "parameter": "kp", "value": 40.0, "justification": "x"},          # no-op
        {"component": "shoulder", "parameter": "kp", "value": 900.0, "justification": "x"},         # out of bounds
        {"component": "ALOHA2.Control.ServoGains", "parameter": "kp", "value": 60.0, "justification": "x"},
        {"component": "j_shoulder", "parameter": "q_max", "value": 1.7, "justification": "x"}], src)
    assert [c["structurally_valid"] for c in out] == [True, False, False, False, False]
    assert out[0]["file"] == "Control/FollowerServoSettings.mo" and out[0]["bounds"] == [1.0, 500.0]
    assert "no change" in out[1]["check"] and "[1, 500]" in out[2]["check"] and "instance name" in out[3]["check"]
    assert out[4]["file"] == "Arms/AlohaVX300s.mo"
    basis = out[4]["semantics"]["basis"]
    if basis.startswith("knowledge graph"):          # ontology-grounded decision (GraphDB available)
        assert "Verified fact from data/urdf/aloha_vx300s.urdf" in out[4]["check"]
        assert out[0]["semantics"]["tunable"] is True and out[0]["semantics"]["evidence_status"] == "Assumed"
    else:                                            # explicit, conservative fallback
        assert "GraphDB unavailable" in out[4]["check"]


def test_dynamic_follower_binds_servo_parameters_to_revision(tmp_path):
    """Gains are Modelica bindings to the simulated revision's Control settings, not injected literals."""
    from kkh.studio.dynamics import generate
    from kkh.studio.models import BASELINE
    from kkh.studio import robotics as R
    store = Store(tmp_path / 's.sqlite')
    data = R.trajectory({'configuration_id': R.CONFIG_ID, 'joint_ids': R.JOINTS, 'time': [0.0, 0.5, 1.0],
                         'q': [[0.0, -0.96, 1.16, 0.0, -0.3, 0.0, 0.0, 0.0224]] * 3})
    pkg = tmp_path / 'p' / 'ALOHA2'
    cfg = generate(pkg, data, 1, BASELINE)
    arm = (pkg / 'DynamicArm.mo').read_text()
    assert 'kp=settings.shoulder.kp' in arm and 'ALOHA2.Control.FollowerServoSettings settings' in arm
    assert 'arm.settings.shoulder.feedforward*nominal.j_shoulder.tau' in (pkg / 'RecordedFollower.mo').read_text()
    assert cfg['servo']['shoulder'] == {'kp': 40.0, 'kd': 4.0, 'actuatorTime': 0.03, 'feedforward': 0.0}
    assert cfg['servo_origin'] == 'revision'


@pytest.mark.omc
def test_failed_validation_cannot_be_accepted_and_rollback_restores(tmp_path):
    import shutil
    from kkh.studio.models import BASELINE
    baseline = tmp_path / 'baseline'
    shutil.copytree(BASELINE, baseline, ignore=shutil.ignore_patterns('*.stl'))
    models = Models(Store(tmp_path / 'state.sqlite'), tmp_path / 'models', baseline)
    w = models.create()
    initial = w['data']['head']
    f = models.directory(w['id']) / 'Control/FollowerServoSettings.mo'
    from kkh.studio.models import digest
    broken = f.read_text().replace('shoulder(kp = 40.0', 'shoulder(kp = 40.0 +', 1)   # syntax error
    models.save(w['id'], 'Control/FollowerServoSettings.mo', broken, digest(f))
    head = models.store.get(w['id'], 'model')['data']['head']
    result = models.validate(w['id'], 'ALOHA2.Experiments.RightArmReach')
    assert not result.get('ok', result.get('check', {}).get('ok', False))
    assert models.store.get(head, 'revision')['data']['status'] != 'validated'
    with pytest.raises(ValueError):
        models.accept(w['id'], head)
    restored = models.restore(w['id'], initial, models.changes(w['id'])['hashes'])
    assert 'kp = 40.0 +' not in f.read_text()
    assert restored['data']['head'] not in (initial, head)                 # rollback is a new revision
    assert models.store.get(w['id'], 'model')['data']['accepted'] is None
