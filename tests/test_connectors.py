import json

import httpx
import pytest

from cupbearer.connectors.airlock_client import (
    DENY_ALL_POLICY,
    SpritesAirlockClient,
    parse_exec_frames,
)
from cupbearer.connectors.box_client import BoxClient
from cupbearer.connectors.gateway import GatewayClient, validate_gateway_path
from cupbearer.connectors.llm_client import LLMError, extract_json
from cupbearer.connectors.telegram_client import TelegramClient
from cupbearer.models import ArtifactKind


def frame(t, payload):
    return bytes([t]) + len(payload).to_bytes(4, "big") + payload


def gateway(transport, provider="custom"):
    return GatewayClient("https://api.sprites.dev/v1/gateway", provider, "conn", api_token="fly-token", transport=transport)


def test_gateway_url_validation():
    assert validate_gateway_path("sprites/x/fs/write") == "sprites/x/fs/write"
    for bad in ["../x", "/x", "x/../y", "https://evil", "x%2e%2e", "x\\y"]:
        with pytest.raises(ValueError):
            validate_gateway_path(bad)


def test_exec_frame_parser_stdout_stderr_exit():
    raw = frame(1, b"out") + frame(2, b"err") + frame(3, (0).to_bytes(4, "big"))
    result = parse_exec_frames(raw)
    assert (result.stdout, result.stderr, result.exit_code) == (b"out", b"err", 0)
    with pytest.raises(ValueError):
        parse_exec_frames(frame(1, b"out"))


@pytest.mark.asyncio
async def test_sprites_airlock_detonate_restores_in_finally_and_sends_no_provider_secrets():
    calls = []
    artifact = {"kind":"script","source":"replay","filename":"x.py","sha256":"a"*64,"size_bytes":1,"content_type":None,"source_id":None,"source_url":None,"received_at":"2026-01-01T00:00:00Z"}
    bundle = {"artifact":artifact,"extracted":{},"rendered_pages":[],"diff_regions":[],"events":[],"network":{"attempted":False,"hosts":[],"blocked_hosts":[]},"canaries":[],"canary_hits":[],"prompt_injection_hits":[],"analyzer_stdout":"","analyzer_stderr":"","sanitized_pdf_path":None,"timed_out":False,"error":None}
    def handler(request):
        calls.append((request.method, request.url.path, request.headers.get("authorization")))
        if request.url.path.endswith("/fs/write"): return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/policy/network"): return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/exec"): return httpx.Response(200, content=frame(1,b"")+frame(3,(0).to_bytes(4,"big")))
        if request.url.path.endswith("/fs/read"): return httpx.Response(200, content=json.dumps(bundle).encode())
        if request.url.path.endswith("/restore"): return httpx.Response(200, text='{"type":"complete"}\n')
        return httpx.Response(404)
    client = SpritesAirlockClient(gateway(httpx.MockTransport(handler)), "cupbearer-airlock", "base")
    got = await client.detonate(b"print(1)", ArtifactKind.SCRIPT, "x.py")
    assert got.artifact.filename == "x.py"
    assert any(c[1].endswith("/restore") for c in calls)
    assert all("telegram" not in (c[2] or "").lower() and "box" not in (c[2] or "").lower() for c in calls)
    assert DENY_ALL_POLICY["rules"][0]["action"] == "deny"


@pytest.mark.asyncio
async def test_box_rejects_unsafe_redirect_and_multipart_orders_attributes_first():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/content") and request.method == "GET":
            return httpx.Response(302, headers={"location": "https://evil.example/file"})
        return httpx.Response(200, json={"entries": []})
    client = BoxClient(gateway(httpx.MockTransport(handler), "box"))
    with pytest.raises(ValueError):
        await client.download_file("123")
    def upload_handler(request):
        requests.append(request); return httpx.Response(200, json={"entries":[{"id":"1"}]})
    client = BoxClient(gateway(httpx.MockTransport(upload_handler), "box"))
    await client.upload_file("folder", "a.pdf", b"pdf")
    body = requests[-1].content
    assert body.index(b'name="attributes"') < body.index(b'name="file"')


def test_llm_extracts_json_and_rejects_non_json():
    assert extract_json('prefix {"answer":"yes"} suffix') == {"answer": "yes"}
    with pytest.raises(LLMError):
        extract_json("no json")


@pytest.mark.asyncio
async def test_telegram_gateway_calls_carry_no_bot_token():
    seen = []
    def handler(request):
        seen.append((request.url.path, request.headers.get("authorization","")))
        if request.url.path.endswith("/sendMessage"):
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})
        return httpx.Response(200, json={"ok": True, "result": {}})
    client = TelegramClient(gateway(httpx.MockTransport(handler), "telegram"))
    result = await client.send_message(1, "hello")
    assert result["message_id"] == 7
    assert seen[0][0].endswith("/sendMessage")
    assert "bot" not in seen[0][1].lower()
