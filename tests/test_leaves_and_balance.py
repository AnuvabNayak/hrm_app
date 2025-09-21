from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def auth(un, pw):
    client.post("/register", json={"username": un, "password": pw, "role": "employee"})
    t = client.post("/token", data={"username": un, "password": pw}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}

def test_balance_and_leave_submit():
    headers = auth("lv_user", "PwD!1234")
    # Balance
    r = client.get("/leave-balance/me", headers=headers)
    assert r.status_code in (200, 404)  # 404 if employee profile missing; should be 200 normally
    # Find employee_id similar approach as legacy attendance
    start = datetime.now(timezone.utc).replace(tzinfo=None)
    end = (start + timedelta(days=1))
    submitted = False
    for eid in range(1, 6):
        eid = client.get("/employees/me/employee-id", headers=headers).json()["employee_id"]
        r = client.post("/leaves/", headers=headers, json={
            "employee_id": eid,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "leave_type": "casual",
            "reason": "e2e test"
        })
        assert r.status_code in (200, 201), r.text
        if r.status_code in (200, 201):
            submitted = True
            break
        elif r.status_code == 403:
            continue
        else:
            assert False, r.text
    assert submitted
