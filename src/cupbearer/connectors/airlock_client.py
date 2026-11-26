from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from ..airlock.cli import run_detonation
from ..airlock.link import is_public_http_url
from ..models import ArtifactKind, ForensicBundle
from .gateway import GatewayClient

DENY_ALL_POLICY = {"rules": [{"domain": "*", "action": "deny"}]}


@dataclass
class ExecResult:
    stdout: bytes
    stderr: bytes
    exit_code: int


def parse_exec_frames(data: bytes) -> ExecResult:
    """Parse Sprites exec frames: type byte, uint32 big-endian length, payload."""
    stdout = bytearray(); stderr = bytearray(); exit_code: int | None = None; pos = 0
    while pos + 5 <= len(data):
        typ = data[pos]; length = int.from_bytes(data[pos + 1:pos + 5], "big"); pos += 5
        payload = data[pos:pos + length]
        if len(payload) != length:
            break
        pos += length
        if typ == 1: stdout.extend(payload)
        elif typ == 2: stderr.extend(payload)
        elif typ == 3: exit_code = int.from_bytes(payload or b"\x00", "big", signed=True)
    if exit_code is None:
        raise ValueError("missing exec exit frame")
    return ExecResult(bytes(stdout), bytes(stderr), exit_code)


class AirlockRunner:
    async def detonate(self, payload: bytes | str, kind: ArtifactKind, filename: str) -> ForensicBundle: ...


class LocalAirlockClient:
    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def detonate(self, payload: bytes | str, kind: ArtifactKind, filename: str) -> ForensicBundle:
        with tempfile.TemporaryDirectory(prefix="cupbearer-local-airlock-") as tmp:
            root = Path(tmp)
            if kind == ArtifactKind.LINK:
                source = payload.decode() if isinstance(payload, bytes) else payload
            else:
                source_path = root / filename
                source_path.write_bytes(payload if isinstance(payload, bytes) else payload.encode())
                source = str(source_path)
            return await asyncio.to_thread(run_detonation, source, root / "out", kind, self.timeout)


class SpritesAirlockClient:
    def __init__(self, gateway: GatewayClient, sprite_name: str, checkpoint_id: str, max_artifact_bytes: int = 16 * 1024 * 1024):
        self.gateway = gateway
        self.sprite_name = sprite_name
        self.checkpoint_id = checkpoint_id
        self.max_artifact_bytes = max_artifact_bytes
        self._lock = asyncio.Lock()

    def _sprite_path(self, suffix: str) -> str:
        return f"sprites/{self.sprite_name}/{suffix.strip('/')}"

    async def write_file(self, remote_path: str, content: bytes) -> None:
        if len(content) > self.max_artifact_bytes:
            raise ValueError("artifact exceeds 16 MiB Sprites fs/write cap")
        r = await self.gateway.request("PUT", self._sprite_path("fs/write"), params={"path": remote_path, "workingDir": "/"}, content=content)
        r.raise_for_status()

    async def exec(self, argv: list[str], stdin: bytes | None = None) -> ExecResult:
        r = await self.gateway.request("POST", self._sprite_path("exec"), params=[("cmd", part) for part in argv], content=stdin or b"")
        r.raise_for_status()
        result = parse_exec_frames(r.content)
        if result.exit_code != 0:
            raise RuntimeError(f"airlock exec exited {result.exit_code}: {result.stderr[-400:]!r}")
        return result

    async def read_file(self, remote_path: str) -> bytes:
        r = await self.gateway.request("GET", self._sprite_path("fs/read"), params={"path": remote_path, "workingDir": "/"})
        r.raise_for_status()
        return r.content

    async def set_network_policy(self, rules: list[dict] | None = None) -> None:
        r = await self.gateway.request("POST", self._sprite_path("policy/network"), json=rules if rules is not None else DENY_ALL_POLICY)
        r.raise_for_status()

    async def restore_checkpoint(self) -> None:
        r = await self.gateway.request("POST", self._sprite_path(f"checkpoints/{self.checkpoint_id}/restore"))
        r.raise_for_status()
        completed = False
        for line in r.text.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "error":
                raise RuntimeError(f"checkpoint restore failed: {event}")
            completed = completed or event.get("type") == "complete"
        if not completed:
            raise RuntimeError("checkpoint restore stream ended before complete")

    async def detonate(self, payload: bytes | str, kind: ArtifactKind, filename: str) -> ForensicBundle:
        if kind != ArtifactKind.LINK:
            raw = payload if isinstance(payload, bytes) else payload.encode()
            if len(raw) > self.max_artifact_bytes:
                raise ValueError("artifact exceeds 16 MiB Sprites fs/write cap")
        else:
            url = payload.decode() if isinstance(payload, bytes) else payload
            if not is_public_http_url(url):
                raise ValueError("link failed SSRF validation")
            raw = url.encode()
        async with self._lock:
            try:
                await self.write_file("/tmp/payload", raw)
                await self.set_network_policy({"rules": []})
                await self.exec(["cupbearer-airlock", "/tmp/payload", "--type", kind.value, "--output", "/tmp/out"])
                data = await self.read_file("/tmp/out/bundle.json")
                return ForensicBundle.model_validate_json(data)
            finally:
                try:
                    await self.set_network_policy()
                finally:
                    await self.restore_checkpoint()
