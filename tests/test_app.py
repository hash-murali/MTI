import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "test.db"
os.environ["TASTE_DB_URL"] = f"sqlite:///{TEST_DB}"

from fastapi.testclient import TestClient
from app.main import app


def setup_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def teardown_module():
    if TEST_DB.exists():
        TEST_DB.unlink()


def test_health_and_seeded_catalog():
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        rows = client.get("/api/catalog").json()
        assert len(rows) >= 15
        assert any(x["title"] == "Steins;Gate" for x in rows)


def test_onboarding_recommendation_feedback_and_export():
    with TestClient(app) as client:
        r = client.post("/api/onboarding", json={"answers":[{"feature":"philosophical_depth","value":.95,"importance":.9,"scope":"global"}]})
        assert r.status_code == 200
        recs = client.post("/api/recommendations", json={"mode":"entertainment","energy":"high","exploration":.4,"limit":5}).json()
        assert len(recs) == 5
        assert all("why" in x and "downsides" in x and "confidence" in x for x in recs)
        media_id = recs[0]["media_id"]
        fb = client.post(f"/api/media/{media_id}/feedback", json={"status":"completed","progress":100,"enjoyment":92,"quality":90,"rewatch_value":80,"aspects":{},"notes":"Strong fit"})
        assert fb.status_code == 200
        assert fb.json()["profile_updated"] is True
        analytics = client.get("/api/analytics").json()
        assert analytics["completed"] == 1
        assert analytics["evaluations"] == 1
        exported = client.get("/api/export").json()
        assert exported["version"] == "1.0"
        assert len(exported["preferences"]) > 0
