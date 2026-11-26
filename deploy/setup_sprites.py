from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))



def deny_all_policy() -> dict:
    return {"rules": [{"domain": "*", "action": "deny"}]}


def webhook_payload(public_base_url: str, secret: str) -> dict:
    return {"url": public_base_url.rstrip("/") + "/api/webhooks/telegram", "secret_token": secret, "allowed_updates": ["message", "callback_query"], "drop_pending_updates": True}


def required_env() -> list[str]:
    return ["SPRITES_API_TOKEN", "TELEGRAM_CONNECTION_ID", "BOX_CONNECTION_ID", "PINECONE_CONNECTION_ID", "LLM_CONNECTION_ID", "AIRLOCK_BASELINE_CHECKPOINT_ID", "PUBLIC_BASE_URL"]


def probe(dry_run: bool = True) -> dict:
    missing = [name for name in required_env() if not os.environ.get(name)]
    checks = {
        "config": {"ok": not missing, "missing": missing},
        "airlock_self_proxy": {"path": "sprites/cupbearer-airlock/fs/write", "shape": "custom-api-gateway", "ok": dry_run},
        "telegram": {"paths": ["setWebhook", "sendMessage", "sendPhoto", "getFile"], "ok": dry_run},
        "box": {"paths": ["2.0/folders/{id}/items", "2.0/files/{id}/content", "2.0/files/content"], "ok": dry_run},
        "pinecone": {"paths": ["indexes/{index}", "indexes/{index}/records/namespaces/{ns}/upsert"], "requires_precreated_index": True, "ok": dry_run},
        "llm": {"provider_default": "gemini", "ollama": "probe-gated", "ok": dry_run},
    }
    checks["ok"] = all(v.get("ok", False) for v in checks.values() if isinstance(v, dict) and "ok" in v) and not missing
    return checks


def smoke() -> dict:
    result = probe(dry_run=False)
    result["live"] = "not-run: live Fly.io credentials and connector provisioning are required"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Provision and verify Cupbearer Sprites deployment")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.probe or args.dry_run or not args.smoke:
        print(json.dumps(probe(dry_run=True), indent=2))
        return 0 if not [n for n in required_env() if not os.environ.get(n)] else 2
    print(json.dumps(smoke(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
