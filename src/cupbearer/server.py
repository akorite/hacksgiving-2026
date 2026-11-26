from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .box_watcher import BoxWatcher
from .config import get_settings
from .connectors.airlock_client import LocalAirlockClient
from .models import ArtifactKind, ArtifactSource, ReplayFixture
from .pipeline import InspectionPipeline
from .store import Store

STATIC = Path(__file__).parent / "server" / "static"


class ChatIn(BaseModel):
    question: str


class ReplayIn(BaseModel):
    fixture_id: str


def load_fixtures(root: Path = Path("tests/fixtures")) -> list[ReplayFixture]:
    return [
        ReplayFixture(id="canary-thief", title="Skill reads planted credentials", kind=ArtifactKind.SCRIPT, path=str(root / "canary_thief.py"), expected_verdict="MALICIOUS", must_hit_canaries=["credential"], notes="prints the credential canary"),
        ReplayFixture(id="benign-note", title="Benign local script", kind=ArtifactKind.SCRIPT, path=str(root / "benign.py"), expected_verdict="INCONCLUSIVE"),
    ]


def create_app(pipeline: InspectionPipeline | None = None, watcher: BoxWatcher | None = None, settings=None) -> FastAPI:
    settings = settings or get_settings()
    store = pipeline.store if pipeline else Store(settings.sqlite_path)
    pipeline = pipeline or InspectionPipeline(store, LocalAirlockClient(settings.airlock_timeout_seconds), artifacts_dir=settings.artifacts_dir)
    app = FastAPI(title="Cupbearer", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.pipeline = pipeline
    app.state.watcher = watcher

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["content-security-policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "no-referrer"
        return response

    @app.get("/")
    def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/i/{inspection_id}")
    def desk(inspection_id: str):
        return FileResponse(STATIC / "index.html")

    @app.get("/api/inspections")
    def inspections():
        return [i.model_dump(mode="json") for i in pipeline.store.list()]

    @app.get("/api/inspections/{inspection_id}")
    def inspection(inspection_id: str):
        item = pipeline.store.get(inspection_id)
        if not item: raise HTTPException(404, "inspection not found")
        return item.model_dump(mode="json")

    @app.get("/api/inspections/{inspection_id}/xray")
    def xray(inspection_id: str):
        item = pipeline.store.get(inspection_id)
        if not item or not item.annotated_png_path or not Path(item.annotated_png_path).exists(): raise HTTPException(404, "xray not found")
        return FileResponse(item.annotated_png_path, media_type="image/png")

    @app.post("/api/inspections/{inspection_id}/chat")
    async def chat(inspection_id: str, body: ChatIn):
        try: return {"answer": await pipeline.answer(inspection_id, body.question)}
        except KeyError: raise HTTPException(404, "inspection not found")

    @app.post("/api/inspections/{inspection_id}/approve")
    async def approve(inspection_id: str):
        try: return (await pipeline.approve(inspection_id)).model_dump(mode="json")
        except KeyError: raise HTTPException(404, "inspection not found")
        except ValueError as exc: raise HTTPException(409, str(exc))

    @app.post("/api/inspections/{inspection_id}/discard")
    async def discard(inspection_id: str):
        try: return (await pipeline.discard(inspection_id)).model_dump(mode="json")
        except KeyError: raise HTTPException(404, "inspection not found")

    @app.get("/api/replay")
    def replay_list():
        return [f.model_dump(mode="json") for f in load_fixtures()]

    @app.post("/api/replay")
    async def replay(body: ReplayIn):
        fixture = next((f for f in load_fixtures() if f.id == body.fixture_id), None)
        if not fixture: raise HTTPException(404, "fixture not found")
        path = Path(fixture.path)
        if not path.exists(): raise HTTPException(404, "fixture payload missing")
        content = path.read_bytes()
        item = await pipeline.inspect_bytes(content, path.name, fixture.kind, ArtifactSource.REPLAY, fixture.id)
        return item.model_dump(mode="json")

    @app.post("/api/sync")
    async def sync():
        if not app.state.watcher: return {"inspections": [], "mode": "local-no-box"}
        return {"inspections": await app.state.watcher.sync_now()}

    @app.post("/api/webhooks/telegram")
    async def telegram(request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)):
        if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
            raise HTTPException(401, "bad webhook secret")
        update = await request.json()
        message = update.get("message") or {}
        doc = message.get("document")
        if doc and doc.get("file_size", 0) <= settings.max_artifact_bytes:
            # Live mode downloads through TelegramClient; webhook shape is verified here without embedding a bot token.
            return {"ok": True, "queued": True, "file_id": doc.get("file_id")}
        callback = update.get("callback_query") or {}
        if callback:
            return {"ok": True, "callback": callback.get("data")}
        return {"ok": True}

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
