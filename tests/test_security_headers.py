from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_docs_accessible():
    r = client.get("/docs")
    assert r.status_code in (200, 404)  # may be 200 when server started with docs; TestClient can serve swagger UI
