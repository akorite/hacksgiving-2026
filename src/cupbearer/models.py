from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArtifactKind(StrEnum):
    PDF = "pdf"
    LINK = "link"
    SCRIPT = "script"
    SKILL = "skill"
    REPO = "repo"


class ArtifactSource(StrEnum):
    BOX = "box"
    TELEGRAM = "telegram"
    REPLAY = "replay"


class VerdictType(StrEnum):
    VERIFIED = "VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    MALICIOUS = "MALICIOUS"
    INCONCLUSIVE = "INCONCLUSIVE"


class InspectionStatus(StrEnum):
    QUARANTINED = "quarantined"
    AWAITING_OWNER = "awaiting_owner"
    VERIFIED = "verified"
    HELD = "held"
    DISCARDED = "discarded"


class Artifact(BaseModel):
    kind: ArtifactKind
    source: ArtifactSource
    filename: str
    sha256: str
    size_bytes: int = Field(ge=0)
    content_type: str | None = None
    source_id: str | None = None
    source_url: str | None = None
    received_at: datetime = Field(default_factory=utcnow)

    @field_validator("sha256")
    @classmethod
    def valid_sha256(cls, value: str) -> str:
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise ValueError("sha256 must be a 64-character hex digest")
        return value.lower()


class CanaryToken(BaseModel):
    value: str
    kind: Literal["credential", "api_key", "beacon_url", "dns_host"]
    label: str
    planted_path: str | None = None


class ExtractedFields(BaseModel):
    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total_amount: str | None = None
    currency: str | None = None
    sender_email: str | None = None
    reply_to: str | None = None
    bank_account: str | None = None
    routing_number: str | None = None
    iban: str | None = None
    payment_url: str | None = None
    raw_text_excerpt: str | None = Field(default=None, max_length=4000)


class ExecEvent(BaseModel):
    type: Literal["process", "file", "network", "signal", "audit"]
    name: str
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=utcnow)


class NetworkActivity(BaseModel):
    attempted: bool = False
    hosts: list[str] = Field(default_factory=list)
    blocked_hosts: list[str] = Field(default_factory=list)


class RenderedPage(BaseModel):
    page: int = Field(ge=1)
    png_path: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DiffRegion(BaseModel):
    page: int = Field(ge=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    kind: str = "visual"
    note: str = ""


class ForensicBundle(BaseModel):
    artifact: Artifact
    extracted: ExtractedFields = Field(default_factory=ExtractedFields)
    rendered_pages: list[RenderedPage] = Field(default_factory=list)
    diff_regions: list[DiffRegion] = Field(default_factory=list)
    events: list[ExecEvent] = Field(default_factory=list)
    network: NetworkActivity = Field(default_factory=NetworkActivity)
    canaries: list[CanaryToken] = Field(default_factory=list)
    canary_hits: list[str] = Field(default_factory=list)
    prompt_injection_hits: list[str] = Field(default_factory=list)
    analyzer_stdout: str = ""
    analyzer_stderr: str = ""
    sanitized_pdf_path: str | None = None
    timed_out: bool = False
    error: str | None = None


class TrustBaseline(BaseModel):
    vendor_name: str
    sender_email: str | None = None
    bank_account: str | None = None
    routing_number: str | None = None
    payment_domain: str | None = None
    invoice_prefix: str | None = None
    source_file_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Verdict(BaseModel):
    verdict: VerdictType
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    llm_degraded: bool = False


class ChatEntry(BaseModel):
    role: Literal["owner", "assistant", "system"]
    text: str
    at: datetime = Field(default_factory=utcnow)


class Inspection(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    artifact: Artifact
    bundle: ForensicBundle | None = None
    verdict: Verdict | None = None
    status: InspectionStatus = InspectionStatus.QUARANTINED
    box_file_id: str | None = None
    telegram_chat_id: int | None = None
    telegram_message_id: int | None = None
    annotated_png_path: str | None = None
    sanitized_pdf_path: str | None = None
    chat: list[ChatEntry] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ActivityEntry(BaseModel):
    inspection_id: str | None = None
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=utcnow)


class ReplayFixture(BaseModel):
    id: str
    title: str
    kind: ArtifactKind
    path: str
    expected_verdict: VerdictType
    must_hit_canaries: list[str] = Field(default_factory=list)
    notes: str = ""
