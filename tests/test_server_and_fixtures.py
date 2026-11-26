from pathlib import Path

from fastapi.testclient import TestClient

from cupbearer.config import Settings
from cupbearer.connectors.airlock_client import LocalAirlockClient
from cupbearer.pipeline import InspectionPipeline
from cupbearer.server import create_app
from cupbearer.store import Store


def client(tmp_path):
    settings = Settings(sqlite_path=tmp_path / "db.sqlite", artifacts_dir=tmp_path / "artifacts", telegram_webhook_secret="secret")
    store = Store(tmp_path / "db.sqlite")
    pipe = InspectionPipeline(store, LocalAirlockClient(timeout=3), artifacts_dir=tmp_path / "artifacts")
    return TestClient(create_app(pipe, settings=settings))


def test_light_table_and_security_headers(tmp_path):
    c = client(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert "script-src 'self'" in r.headers["content-security-policy"]
    js = Path("src/cupbearer/server/static/app.js").read_text()
    assert "innerHTML" not in js


def test_replay_api_creates_persistent_inspection_and_actions(tmp_path):
    c = client(tmp_path)
    fixtures = c.get("/api/replay").json()
    assert any(f["id"] == "canary-thief" for f in fixtures)
    created = c.post("/api/replay", json={"fixture_id": "canary-thief"})
    assert created.status_code == 200
    item = created.json()
    assert item["verdict"]["verdict"] in {"MALICIOUS", "SUSPICIOUS", "INCONCLUSIVE"}
    assert c.get("/api/inspections/" + item["id"]).status_code == 200
    assert c.get("/api/inspections/" + item["id"] + "/xray").headers["content-type"] == "image/png"
    chat = c.post("/api/inspections/" + item["id"] + "/chat", json={"question": "why?"})
    assert chat.status_code == 200 and chat.json()["answer"]
    assert c.post("/api/inspections/missing/approve").status_code == 404
    assert c.post("/api/inspections/" + item["id"] + "/discard").json()["status"] == "discarded"


def test_telegram_webhook_secret_and_document_shape(tmp_path):
    c = client(tmp_path)
    assert c.post("/api/webhooks/telegram", json={}).status_code == 401
    update = {"message": {"document": {"file_id": "abc", "file_size": 10}}}
    r = c.post("/api/webhooks/telegram", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "secret"})
    assert r.status_code == 200 and r.json()["file_id"] == "abc"
