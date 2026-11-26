from __future__ import annotations

from .gateway import GatewayClient

API_VERSION = "2026-07"


class PineconeClient:
    def __init__(self, gateway: GatewayClient, index_host: str | None, index_name: str):
        self.gateway = gateway; self.index_host = (index_host or "").rstrip("/"); self.index_name = index_name

    def _headers(self) -> dict[str, str]:
        return {"X-Pinecone-Api-Version": API_VERSION, "Authorization": "Bearer sprites-gateway"}

    def _path(self, suffix: str) -> str:
        return f"indexes/{self.index_name}/{suffix.strip('/')}"

    async def verify_index(self) -> bool:
        r = await self.gateway.request("GET", "indexes/" + self.index_name, headers=self._headers())
        if r.status_code == 404:
            raise RuntimeError("Pinecone index missing; pre-create the Starter integrated-embedding index in the Pinecone console")
        r.raise_for_status(); return True

    async def upsert_record(self, namespace: str, record_id: str, text: str, metadata: dict) -> None:
        payload = {"records": [{"_id": record_id, "chunk_text": text, **metadata}]}
        r = await self.gateway.request("POST", self._path(f"records/namespaces/{namespace}/upsert"), json=payload, headers=self._headers())
        r.raise_for_status()

    async def search(self, namespace: str, text: str, top_k: int = 3) -> list[dict]:
        payload = {"query": {"inputs": {"text": text}, "top_k": top_k}, "fields": ["chunk_text"]}
        r = await self.gateway.request("POST", self._path(f"records/namespaces/{namespace}/search"), json=payload, headers=self._headers())
        r.raise_for_status()
        return r.json().get("result", {}).get("hits", [])
