from __future__ import annotations

import re
from urllib.parse import quote

import httpx

_SAFE = re.compile(r"^[A-Za-z0-9._~/-]+$")


def validate_gateway_path(path: str) -> str:
    if not path or path.startswith("/") or "://" in path or ".." in path or "%2e" in path.lower() or "\\" in path:
        raise ValueError("unsafe gateway path")
    if not _SAFE.match(path):
        raise ValueError("gateway path contains unsafe characters")
    return path


class GatewayClient:
    """Thin Sprites Connectors Gateway client. Provider credentials remain inside Fly.io."""

    def __init__(self, base_url: str, provider: str, connection_id: str, api_token: str | None = None, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.connection_id = connection_id
        headers = {"Authorization": f"Bearer {api_token}"} if api_token else {}
        self.client = httpx.AsyncClient(transport=transport, headers=headers, timeout=30)

    def url(self, path: str) -> str:
        validate_gateway_path(path)
        provider = quote(self.provider, safe="")
        connection = quote(self.connection_id, safe="")
        return f"{self.base_url}/{provider}/{connection}/{path}"

    async def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = await self.client.request(method, self.url(path), **kwargs)
        return response

    async def aclose(self) -> None:
        await self.client.aclose()
