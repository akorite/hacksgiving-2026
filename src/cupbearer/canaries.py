from __future__ import annotations

import secrets
from pathlib import Path

from .models import CanaryToken


def new_canaries(prefix: str = "cb") -> list[CanaryToken]:
    nonce = secrets.token_hex(5)
    return [
        CanaryToken(value=f"{prefix}-cred-{nonce}", kind="credential", label="fake password", planted_path="canary/credentials.txt"),
        CanaryToken(value=f"{prefix}-key-{nonce}", kind="api_key", label="fake API key", planted_path="canary/api.key"),
        CanaryToken(value=f"https://{nonce}.canary.cupbearer.invalid/beacon", kind="beacon_url", label="HTTP beacon"),
        CanaryToken(value=f"{nonce}.dns.cupbearer.invalid", kind="dns_host", label="DNS beacon"),
    ]


def plant_canaries(root: Path, canaries: list[CanaryToken]) -> None:
    canary_dir = root / "canary"
    canary_dir.mkdir(parents=True, exist_ok=True)
    for token in canaries:
        if token.planted_path:
            path = root / token.planted_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{token.label}: {token.value}\n", encoding="utf-8")
        elif token.kind == "beacon_url":
            (canary_dir / "beacon.url").write_text(token.value + "\n", encoding="utf-8")
        elif token.kind == "dns_host":
            (canary_dir / "dns.host").write_text(token.value + "\n", encoding="utf-8")


def scan_canaries(text: str, canaries: list[CanaryToken]) -> list[str]:
    return [token.value for token in canaries if token.value and token.value in text]
