from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..models import Artifact, ArtifactKind, ArtifactSource
from .link import analyze_link
from .pdf import analyze_pdf
from .script import analyze_script


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_kind(path_or_url: str) -> ArtifactKind:
    if path_or_url.startswith(("http://", "https://")):
        return ArtifactKind.LINK
    suffix = Path(path_or_url).suffix.lower()
    if suffix == ".pdf":
        return ArtifactKind.PDF
    if suffix in {".py", ".sh", ".bash", ".ps1", ".js", ".exe"}:
        return ArtifactKind.SCRIPT
    return ArtifactKind.SKILL if Path(path_or_url).is_dir() else ArtifactKind.SCRIPT


def run_detonation(path_or_url: str, output: Path, kind: ArtifactKind | None = None, timeout: int = 15):
    kind = kind or detect_kind(path_or_url)
    output.mkdir(parents=True, exist_ok=True)
    if kind == ArtifactKind.LINK:
        artifact = Artifact(kind=kind, source=ArtifactSource.REPLAY, filename=path_or_url, sha256=hashlib.sha256(path_or_url.encode()).hexdigest(), size_bytes=0, source_url=path_or_url)
        bundle = analyze_link(path_or_url, output, artifact, timeout=max(timeout, 25))
    else:
        path = Path(path_or_url)
        artifact = Artifact(kind=kind, source=ArtifactSource.REPLAY, filename=path.name, sha256=sha256_file(path) if path.is_file() else hashlib.sha256(str(path).encode()).hexdigest(), size_bytes=path.stat().st_size if path.is_file() else 0)
        bundle = analyze_pdf(path, output, artifact) if kind == ArtifactKind.PDF else analyze_script(path, output, artifact, timeout=timeout)
    (output / "bundle.json").write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    return bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cupbearer Airlock local detonator")
    parser.add_argument("input", help="payload path or URL")
    parser.add_argument("--type", choices=[k.value for k in ArtifactKind], default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--phase", choices=["fetch", "detonate"], default="detonate")
    args = parser.parse_args(argv)
    kind = ArtifactKind(args.type) if args.type else None
    bundle = run_detonation(args.input, args.output, kind, args.timeout)
    print(json.dumps({"error": bundle.error, "timed_out": bundle.timed_out, "canary_hits": len(bundle.canary_hits)}))
    return 1 if bundle.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
