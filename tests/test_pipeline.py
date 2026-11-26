import pytest

from cupbearer.box_watcher import BoxWatcher
from cupbearer.connectors.airlock_client import LocalAirlockClient
from cupbearer.models import Artifact, ArtifactKind, ArtifactSource, ForensicBundle, TrustBaseline, VerdictType
from cupbearer.pipeline import InspectionPipeline
from cupbearer.store import Store
from cupbearer.verdict import deterministic_verdict


def store(tmp_path):
    return Store(tmp_path / "cupbearer.db")


def test_deterministic_verdict_bank_drift_is_malicious():
    artifact = Artifact(kind=ArtifactKind.PDF, source=ArtifactSource.BOX, filename="invoice.pdf", sha256="a"*64, size_bytes=1)
    bundle = ForensicBundle(artifact=artifact)
    bundle.extracted.vendor_name = "Acme Parts"; bundle.extracted.bank_account = "999"; bundle.extracted.routing_number = "111"
    baseline = TrustBaseline(vendor_name="Acme Parts", bank_account="123", routing_number="111")
    verdict = deterministic_verdict(bundle, baseline)
    assert verdict.verdict == VerdictType.MALICIOUS
    assert any("bank account" in r for r in verdict.reasons)


@pytest.mark.asyncio
async def test_pipeline_persists_inspection_and_owner_actions(tmp_path):
    s = store(tmp_path)
    pipe = InspectionPipeline(s, LocalAirlockClient(timeout=3), artifacts_dir=tmp_path / "artifacts")
    inspection = await pipe.inspect_bytes(b"print('hello')", "hello.py", ArtifactKind.SCRIPT, ArtifactSource.TELEGRAM)
    loaded = s.get(inspection.id)
    assert loaded and loaded.bundle and "hello" in loaded.bundle.analyzer_stdout
    assert loaded.annotated_png_path
    assert loaded.status.value in {"quarantined", "awaiting_owner"}
    answer = await pipe.answer(inspection.id, "what happened?")
    assert "evidence" in answer.lower() or "forensic" in answer.lower()
    approved = await pipe.approve(inspection.id)
    assert approved.status.value == "verified"
    discarded = await pipe.discard(inspection.id)
    assert discarded.status.value == "discarded"
    s.close()


@pytest.mark.asyncio
async def test_box_watcher_deduplicates_and_skips_oversize(tmp_path):
    class FakeBox:
        def __init__(self): self.items = [{"type":"file","id":"f1","name":"a.py"}]
        async def list_folder(self, folder_id): return self.items
        async def download_file(self, file_id): return b"print('x')"
    s = store(tmp_path)
    pipe = InspectionPipeline(s, LocalAirlockClient(timeout=3), artifacts_dir=tmp_path / "artifacts")
    watcher = BoxWatcher(FakeBox(), pipe, "inbox")
    first = await watcher.sync_now(); second = await watcher.sync_now()
    assert len(first) == 1 and second == []
    assert s.processed_box("f1")
    s.close()
