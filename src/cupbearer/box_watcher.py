from __future__ import annotations

import asyncio
import hashlib

from .models import ArtifactKind, ArtifactSource
from .pipeline import InspectionPipeline


def kind_for_name(name: str) -> ArtifactKind:
    lower = name.lower()
    if lower.endswith(".pdf"): return ArtifactKind.PDF
    if lower.endswith((".py", ".sh", ".ps1", ".js")): return ArtifactKind.SCRIPT
    return ArtifactKind.SKILL


class BoxWatcher:
    def __init__(self, box, pipeline: InspectionPipeline, inbox_folder_id: str, interval: int = 300):
        self.box = box; self.pipeline = pipeline; self.inbox_folder_id = inbox_folder_id; self.interval = interval; self._wake = asyncio.Event(); self._stopped = asyncio.Event()

    async def sync_now(self) -> list[str]:
        made = []
        for item in await self.box.list_folder(self.inbox_folder_id):
            if item.get("type") != "file" or self.pipeline.store.processed_box(item["id"]):
                continue
            try:
                content = await self.box.download_file(item["id"])
                sha = hashlib.sha256(content).hexdigest()
                inspection = await self.pipeline.inspect_bytes(content, item.get("name", "artifact"), kind_for_name(item.get("name", "")), ArtifactSource.BOX, item["id"])
                self.pipeline.store.mark_box(item["id"], sha, inspection.status.value)
                made.append(inspection.id)
            except ValueError as exc:
                self.pipeline.store.mark_box(item["id"], "unknown", "skipped:" + str(exc)[:120])
        return made

    async def run(self) -> None:
        while not self._stopped.is_set():
            await self.sync_now()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self.interval)
                self._wake.clear()
            except TimeoutError:
                pass

    async def stop(self) -> None:
        self._stopped.set(); self._wake.set()
