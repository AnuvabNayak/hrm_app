from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_register_and_login_and_me():
    # Register a fresh user
    uname = "e2e_user"
    pwd = "e2e_pass123"
    r = client.post("/register", json={"username": uname, "password": pwd, "role": "employee"})
    assert r.status_code in (200, 400)  # 400 if already registered
    # Login
    r = client.post("/token", data={"username": uname, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    # users/me
    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    me = r.json()
    assert me["username"] == uname
    assert me["role"] in ("employee", "admin", "super_admin")