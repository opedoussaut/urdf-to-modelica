from fastapi.testclient import TestClient
from kkh.api.main import app

client = TestClient(app)


def test_browser_evidence_flow():
    studio = client.get("/api/studio").json()
    assert studio["baseline"]["success"]
    run_id = studio["baseline"]["run_id"]
    result = client.get(f"/api/runs/{run_id}/results")
    assert result.status_code == 200
    data = result.json()
    assert data["time"][-1] == 9
    assert len(data["links"]["follower_right/ee_gripper_link"]) == len(data["time"])
    geometry = client.get("/api/geometry").json()
    assert geometry
    assert client.get(geometry[0]["mesh"]).status_code == 200


def test_api_rejects_cross_origin_jobs_and_unknown_models():
    assert client.post("/api/runs", json={"experiment": "RightArmReach"}, headers={"origin": "https://example.com"}).status_code == 403
    assert client.post("/api/runs", json={"experiment": "Arbitrary.Class"}).status_code == 422
    assert client.get("/api/runs/..%5C..%5Csecret/results").status_code == 400
    assert client.get("/api/jobs/not-a-job").status_code == 404
