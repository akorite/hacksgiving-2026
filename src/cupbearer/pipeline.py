from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from .annotator import annotate_xray
from .connectors.llm_client import LLMError
from .models import (
    Artifact,
    ArtifactKind,
    ArtifactSource,
    ChatEntry,
    Inspection,
    InspectionStatus,
    TrustBaseline,
    VerdictType,
)
from .store import Store
from .verdict import deterministic_verdict


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InspectionPipeline:
    def __init__(self, store: Store, airlock, box=None, pinecone=None, llm=None, artifacts_dir: Path = Path("data/artifacts")):
        self.store = store; self.airlock = airlock; self.box = box; self.pinecone = pinecone; self.llm = llm; self.artifacts_dir = artifacts_dir

    async def inspect_bytes(self, content: bytes, filename: str, kind: ArtifactKind, source: ArtifactSource, source_id: str | None = None) -> Inspection:
        artifact = Artifact(kind=kind, source=source, filename=filename, sha256=sha256_bytes(content), size_bytes=len(content), source_id=source_id)
        inspection = Inspection(artifact=artifact)
        self.store.save(inspection)
        bundle = await self.airlock.detonate(content, kind, filename)
        inspection.bundle = bundle
        baseline = await self.trust_baseline_for(bundle.extracted.vendor_name)
        verdict = deterministic_verdict(bundle, baseline)
        llm_degraded = False
        if self.llm:
            try:
                brief = await self.llm.verdict_brief({"extracted": bundle.extracted.model_dump(), "signals": verdict.model_dump()})
                if isinstance(brief.get("summary"), str):
                    verdict.reasons.append(brief["summary"])
            except LLMError:
                llm_degraded = True
        verdict.llm_degraded = llm_degraded
        inspection.verdict = verdict
        inspection.status = InspectionStatus.QUARANTINED if verdict.verdict in {VerdictType.MALICIOUS, VerdictType.INCONCLUSIVE} else InspectionStatus.AWAITING_OWNER
        outdir = self.artifacts_dir / inspection.id
        inspection.annotated_png_path = str(annotate_xray(bundle, verdict.verdict, outdir / "xray.png"))
        if bundle.sanitized_pdf_path:
            inspection.sanitized_pdf_path = bundle.sanitized_pdf_path
        inspection.updated_at = datetime.now(UTC)
        return self.store.save(inspection)

    async def trust_baseline_for(self, vendor_name: str | None) -> TrustBaseline | None:
        if not vendor_name or not self.pinecone:
            return None
        try:
            hits = await self.pinecone.search("trust-baseline", vendor_name, top_k=1)
        except (RuntimeError, ValueError, KeyError, TypeError):
            return None
        if not hits:
            return None
        fields = hits[0].get("fields", hits[0])
        try:
            return TrustBaseline(vendor_name=fields.get("vendor_name") or vendor_name, sender_email=fields.get("sender_email"), bank_account=fields.get("bank_account"), routing_number=fields.get("routing_number"), payment_domain=fields.get("payment_domain"))
        except (RuntimeError, ValueError, KeyError, TypeError):
            return None

    async def answer(self, inspection_id: str, question: str) -> str:
        inspection = self.require(inspection_id)
        inspection.chat.append(ChatEntry(role="owner", text=question))
        answer = "The deterministic forensic evidence is shown in the X-Ray and verdict reasons."
        if self.llm and inspection.bundle:
            try:
                answer = await self.llm.answer_question(question, {"extracted": inspection.bundle.extracted.model_dump(), "verdict": inspection.verdict.model_dump() if inspection.verdict else {}})
            except LLMError:
                answer = "LLM synthesis is degraded; use the deterministic evidence shown in the X-Ray."
        inspection.chat.append(ChatEntry(role="assistant", text=answer))
        inspection.updated_at = datetime.now(UTC); self.store.save(inspection)
        return answer

    async def approve(self, inspection_id: str) -> Inspection:
        inspection = self.require(inspection_id)
        if inspection.verdict and inspection.verdict.verdict == VerdictType.MALICIOUS:
            raise ValueError("malicious artifacts cannot be promoted")
        inspection.status = InspectionStatus.VERIFIED; inspection.updated_at = datetime.now(UTC)
        return self.store.save(inspection)

    async def discard(self, inspection_id: str) -> Inspection:
        inspection = self.require(inspection_id)
        inspection.status = InspectionStatus.DISCARDED; inspection.updated_at = datetime.now(UTC)
        return self.store.save(inspection)

    def require(self, inspection_id: str) -> Inspection:
        inspection = self.store.get(inspection_id)
        if not inspection:
            raise KeyError(inspection_id)
        return inspection
