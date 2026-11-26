from pathlib import Path

import pytest
from pydantic import ValidationError

from cupbearer.canaries import new_canaries, plant_canaries, scan_canaries
from cupbearer.config import Settings
from cupbearer.models import (
    Artifact,
    ArtifactKind,
    ArtifactSource,
    ForensicBundle,
    Verdict,
    VerdictType,
)


def artifact() -> Artifact:
    return Artifact(kind=ArtifactKind.PDF, source=ArtifactSource.BOX, filename="invoice.pdf", sha256="a" * 64, size_bytes=12)


def test_forensic_models_round_trip():
    a = artifact()
    bundle = ForensicBundle(artifact=a)
    verdict = Verdict(verdict=VerdictType.SUSPICIOUS, confidence=0.72, reasons=["sender drift"])
    data = bundle.model_dump_json()
    assert "invoice.pdf" in data
    assert verdict.verdict == VerdictType.SUSPICIOUS
    assert verdict.confidence == 0.72


def test_sha256_validator_rejects_bad_digest():
    with pytest.raises(ValidationError):
        artifact().model_copy(update={"sha256": "not-a-sha"}).model_validate(artifact().model_copy(update={"sha256": "not-a-sha"}).model_dump())
    with pytest.raises(ValidationError):
        Artifact(kind=ArtifactKind.PDF, source=ArtifactSource.BOX, filename="x", sha256="bad", size_bytes=1)


def test_canaries_plant_and_scan(tmp_path: Path):
    canaries = new_canaries("test")
    plant_canaries(tmp_path, canaries)
    planted = "\n".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    hits = scan_canaries(planted, canaries)
    assert set(hits) == {c.value for c in canaries}
    assert len(canaries) == 4
    assert len({c.value for c in canaries}) == 4


def test_settings_defaults_enforce_zero_secret_mode_and_16mib_cap(tmp_path):
    s = Settings(sqlite_path=tmp_path / "db.sqlite", artifacts_dir=tmp_path / "artifacts")
    assert s.max_artifact_bytes == 16 * 1024 * 1024
    assert s.llm_provider == "gemini"
    assert s.sprites_gateway_base.startswith("https://api.sprites.dev/")
    with pytest.raises(ValidationError):
        Settings(max_artifact_bytes=16 * 1024 * 1024 + 1)
    with pytest.raises(ValidationError):
        Settings(llm_provider="typesafe")
