from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def auth(un, pw):
    client.post("/register", json={"username": un, "password": pw, "role": "employee"})
    t = client.post("/token", data={"username": un, "password": pw}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}

def test_attendance_log_and_list():
    headers = auth("legacy_att", "Pwd#12345")
    # Find employee_id of current user via protected employees list? Employees list is admin-only.
    # Instead, create a dummy log by first retrieving /users/me role-> employee; then POST /attendance/log using the known employee row created at registration equals user_id mapping.
    # For demo, assume employee_id = 1 if it’s the first created; otherwise, you have to query DB or add an endpoint. This test tries a small range.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    found = False
    for eid in range(1, 6):
        eid = client.get("/employees/me/employee-id", headers=headers).json()["employee_id"]
        r = client.post("/attendance/log", headers=headers, json={
            "employee_id": eid,
            "login_time": now.isoformat(),
            "logout_time": (now + timedelta(hours=2)).isoformat(),
            "on_leave": False,
            # "work_hours": None
        })
        if r.status_code in (200, 201):
            found = True
            break
        elif r.status_code == 403:
            continue
        else:
            assert False, r.text
    assert found, "Could not find owned employee_id"
    # List own attendance
    r = client.get("/attendance/", headers=headers)
    assert r.status_code == 200
    rows = r.json()
    assert isinstance(rows, list)
    if rows:
        assert "work_duration" in rows
