from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..canaries import new_canaries, plant_canaries, scan_canaries
from ..models import Artifact, ExecEvent, ForensicBundle, NetworkActivity

NETWORK_MARKERS = ("socket.", "urllib.request", "requests.", "httpx.", "curl ", "wget ", "Invoke-WebRequest")


def command_for(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return [sys.executable, str(path)]
    if suffix in {".sh", ".bash"}:
        shell = shutil.which("bash") or shutil.which("sh")
        if shell:
            return [shell, str(path)]
    if suffix in {".ps1"}:
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell:
            return [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    return [str(path)]


def analyze_script(path: Path, outdir: Path, artifact: Artifact, timeout: int = 15) -> ForensicBundle:
    bundle = ForensicBundle(artifact=artifact)
    canaries = new_canaries()
    bundle.canaries = canaries
    outdir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cupbearer-detonate-") as tmp:
        root = Path(tmp)
        plant_canaries(root, canaries)
        target = root / path.name
        if path.is_dir():
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target)
        bundle.events.append(ExecEvent(type="process", name="spawn", detail={"argv": command_for(target)}))
        try:
            proc = subprocess.run(command_for(target), check=False, cwd=root, capture_output=True, text=True, timeout=timeout, shell=False)
            bundle.analyzer_stdout = proc.stdout[-8000:]
            bundle.analyzer_stderr = proc.stderr[-8000:]
            bundle.events.append(ExecEvent(type="process", name="exit", detail={"returncode": proc.returncode, "duration_ms": int((time.monotonic() - started) * 1000)}))
        except subprocess.TimeoutExpired as exc:
            bundle.timed_out = True
            bundle.analyzer_stdout = (exc.stdout or "")[-8000:] if isinstance(exc.stdout, str) else ""
            bundle.analyzer_stderr = (exc.stderr or "")[-8000:] if isinstance(exc.stderr, str) else ""
            bundle.events.append(ExecEvent(type="signal", name="timeout", detail={"seconds": timeout}))
        observable = bundle.analyzer_stdout + "\n" + bundle.analyzer_stderr
        try:
            observable += "\n" + "\n".join(p.read_text(errors="ignore")[:20000] for p in root.rglob("*") if p.is_file() and "canary" not in p.parts and p.stat().st_size < 20000)
        except (OSError, UnicodeError):
            bundle.events.append(ExecEvent(type="file", name="source-scan-unavailable"))
        bundle.canary_hits = scan_canaries(observable, canaries)
        markers = [m for m in NETWORK_MARKERS if m in observable]
        hosts = sorted({c.value for c in canaries if c.kind in {"beacon_url", "dns_host"} and c.value in observable})
        bundle.network = NetworkActivity(attempted=bool(markers or hosts), hosts=hosts, blocked_hosts=hosts)
        if markers:
            bundle.events.append(ExecEvent(type="network", name="network-marker", detail={"markers": markers}))
    (outdir / "stdout.txt").write_text(bundle.analyzer_stdout, encoding="utf-8")
    (outdir / "stderr.txt").write_text(bundle.analyzer_stderr, encoding="utf-8")
    return bundle
