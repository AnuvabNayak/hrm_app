from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_inspiration_today():
    # Reuse an auth token from a quick register/login
    uname = "insp_user"
    pwd = "xYz!1234"
    client.post("/register", json={"username": uname, "password": pwd, "role": "employee"})
    tok = client.post("/token", data={"username": uname, "password": pwd}).json()["access_token"]
    r = client.get("/inspiration/today", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert "text" in data and "author" in data
