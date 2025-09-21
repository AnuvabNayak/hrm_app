from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def auth(un, pw):
    client.post("/register", json={"username": un, "password": pw, "role": "employee"})
    t = client.post("/token", data={"username": un, "password": pw}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}

def test_rt_flow():
    headers = auth("rt_user", "Pwd#Rt123")
    # Baseline: no active session
    r = client.get("/attendance-rt/active", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] is None
    # Clock-in
    r = client.post("/attendance-rt/clock-in", headers=headers)
    assert r.status_code == 200
    sid = r.json()["session_id"]
    # Start break
    r = client.post("/attendance-rt/start-break", headers=headers)
    assert r.status_code == 200
    assert r.json()["session_id"] == sid
    # Stop break
    r = client.post("/attendance-rt/stop-break", headers=headers)
    assert r.status_code == 200
    # Clock-out
    r = client.post("/attendance-rt/clock-out", headers=headers)
    assert r.status_code == 200
    assert r.json()["session_id"] == sid
    # Recent
    r = client.get("/attendance-rt/recent?days=14", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
