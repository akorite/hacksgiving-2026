from __future__ import annotations

import json
from urllib.parse import urlparse

import httpx

from .gateway import GatewayClient


class BoxClient:
    def __init__(self, gateway: GatewayClient, max_bytes: int = 16 * 1024 * 1024):
        self.gateway = gateway; self.max_bytes = max_bytes

    async def list_folder(self, folder_id: str) -> list[dict]:
        r = await self.gateway.request("GET", f"2.0/folders/{folder_id}/items")
        r.raise_for_status(); return r.json().get("entries", [])

    async def download_file(self, file_id: str) -> bytes:
        r = await self.gateway.request("GET", f"2.0/files/{file_id}/content", follow_redirects=False)
        if r.status_code in {301, 302, 303, 307, 308}:
            target = r.headers.get("location", "")
            host = urlparse(target).hostname or ""
            if not target.startswith("https://") or not (host == "boxcloud.com" or host.endswith(".boxcloud.com")):
                raise ValueError("unsafe Box download redirect")
            async with httpx.AsyncClient(timeout=30) as plain:
                r = await plain.get(target)
        r.raise_for_status()
        if len(r.content) > self.max_bytes:
            raise ValueError("file exceeds Cupbearer 16 MiB artifact cap")
        return r.content

    async def update_file(self, file_id: str, *, tags: list[str] | None = None, description: str | None = None, parent_id: str | None = None) -> dict:
        payload = {}
        if tags is not None: payload["tags"] = tags
        if description is not None: payload["description"] = description
        if parent_id is not None: payload["parent"] = {"id": parent_id}
        r = await self.gateway.request("PUT", f"2.0/files/{file_id}", json=payload)
        r.raise_for_status(); return r.json()

    async def upload_file(self, folder_id: str, filename: str, content: bytes) -> dict:
        if len(content) > 50 * 1024 * 1024:
            raise ValueError("Box direct upload limit is 50 MiB")
        attrs = json.dumps({"name": filename, "parent": {"id": folder_id}})
        files = [("attributes", (None, attrs, "application/json")), ("file", (filename, content, "application/octet-stream"))]
        r = await self.gateway.request("POST", "2.0/files/content", files=files)
        r.raise_for_status(); return r.json()
