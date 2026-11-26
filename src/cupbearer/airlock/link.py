from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..models import Artifact, ExecEvent, ForensicBundle, NetworkActivity


def is_public_http_url(url: str, allowed_hosts: set[str] | None = None) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if allowed_hosts and host in allowed_hosts:
        return True
    if host in {"localhost", "api.sprites.dev"} or host.endswith(".internal"):
        return False
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
    except (OSError, ValueError):
        return False
    return True


def analyze_link(url: str, outdir: Path, artifact: Artifact, timeout: int = 25, max_redirects: int = 5) -> ForensicBundle:
    """Capture link metadata without executing browser scripts in local fallback mode.

    The production Airlock image can use the same bundle shape with Playwright; the local
    implementation intentionally performs only bounded HTTP capture so tests never depend on a browser.
    """
    bundle = ForensicBundle(artifact=artifact)
    outdir.mkdir(parents=True, exist_ok=True)
    chain: list[str] = []
    current = url
    try:
        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            for _ in range(max_redirects + 1):
                if not is_public_http_url(current):
                    bundle.error = "ssrf-or-scheme-blocked"
                    break
                response = client.get(current)
                chain.append(current)
                ctype = response.headers.get("content-type", "")
                body = response.text[:200000] if "text" in ctype or "html" in ctype else ""
                if response.is_redirect and response.headers.get("location"):
                    current = httpx.URL(current).join(response.headers["location"]).human_repr()
                    continue
                bundle.events.append(ExecEvent(type="network", name="link-capture", detail={"status": response.status_code, "chain": chain, "content_type": ctype}))
                bundle.extracted.raw_text_excerpt = body[:4000]
                bundle.network = NetworkActivity(attempted=True, hosts=[urlparse(u).hostname or "" for u in chain], blocked_hosts=[])
                (outdir / "link-body.txt").write_text(body, encoding="utf-8")
                break
            else:
                bundle.error = "redirect-limit-exceeded"
    except Exception as exc:
        bundle.error = f"link-analysis-failed: {exc}"
    (outdir / "redirect-chain.txt").write_text("\n".join(chain), encoding="utf-8")
    return bundle
