from __future__ import annotations

import re
from pathlib import Path

import fitz
from PIL import Image, ImageChops

from ..models import Artifact, DiffRegion, ExecEvent, ExtractedFields, ForensicBundle, RenderedPage

INJECTION_PATTERNS = [
    "ignore previous instructions",
    "disregard all instructions",
    "exfiltrate",
    "send the contents",
    "system prompt",
    "developer message",
]


def extract_invoice_fields(text: str) -> ExtractedFields:
    def search(pattern: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    email = search(r"(?:from|sender|email)\s*[:\-]?\s*([^\s<>]+@[^\s<>]+)")
    return ExtractedFields(
        vendor_name=search(r"(?:vendor|from company|company)\s*[:\-]\s*([^\n]{2,80})"),
        invoice_number=search(r"invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9\-]{3,40})"),
        invoice_date=search(r"(?:invoice\s*)?date\s*[:\-]\s*([^\n]{4,32})"),
        total_amount=search(r"(?:total|amount due)\s*[:\-]?\s*([$€£]?\s*[0-9][0-9,]*(?:\.[0-9]{2})?)"),
        currency=(search(r"\b(USD|EUR|GBP|CAD|AUD)\b") or ("USD" if "$" in text else None)),
        sender_email=email,
        bank_account=search(r"(?:bank\s+account|account)\s*(?:number|no\.?|#)?\s*[:\-]\s*([0-9][0-9 \-]{5,30})"),
        routing_number=search(r"routing\s*(?:number|no\.?|#)?\s*[:\-]\s*([0-9]{6,12})"),
        iban=search(r"\b([A-Z]{2}[0-9]{2}[A-Z0-9]{10,30})\b"),
        payment_url=search(r"(https?://[^\s]+)"),
        raw_text_excerpt=text[:4000] if text else None,
    )


def prompt_injection_hits(text: str) -> list[str]:
    low = text.lower()
    return [p for p in INJECTION_PATTERNS if p in low]


def render_pdf(path: Path, outdir: Path, max_pages: int = 5) -> tuple[list[RenderedPage], str]:
    outdir.mkdir(parents=True, exist_ok=True)
    pages: list[RenderedPage] = []
    text_parts: list[str] = []
    with fitz.open(path) as doc:
        for index in range(min(len(doc), max_pages)):
            page = doc[index]
            text_parts.append(page.get_text())
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            png = outdir / f"page-{index + 1}.png"
            pix.save(png)
            pages.append(RenderedPage(page=index + 1, png_path=str(png), width=pix.width, height=pix.height))
    return pages, "\n".join(text_parts)


def sanitize_pdf(path: Path, outdir: Path, max_pages: int = 5) -> Path:
    """Create a raster-only PDF so active PDF content cannot survive promotion."""
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / "sanitized.pdf"
    with fitz.open(path) as src, fitz.open() as dst:
        for index in range(min(len(src), max_pages)):
            pix = src[index].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            page = dst.new_page(width=pix.width, height=pix.height)
            page.insert_image(page.rect, pixmap=pix)
        dst.save(target, garbage=4, deflate=True)
    return target


def image_diff_regions(before_png: Path, after_png: Path, page: int = 1) -> list[DiffRegion]:
    if not before_png.exists() or not after_png.exists():
        return []
    a = Image.open(before_png).convert("RGB")
    b = Image.open(after_png).convert("RGB")
    if a.size != b.size:
        return [DiffRegion(page=page, x=0, y=0, width=max(a.width, b.width), height=max(a.height, b.height), kind="geometry", note="render dimensions differ")]
    box = ImageChops.difference(a, b).getbbox()
    if not box:
        return []
    x0, y0, x1, y1 = box
    return [DiffRegion(page=page, x=x0, y=y0, width=x1 - x0, height=y1 - y0, kind="visual", note="rendered pixels differ")]


def analyze_pdf(path: Path, outdir: Path, artifact: Artifact) -> ForensicBundle:
    bundle = ForensicBundle(artifact=artifact)
    try:
        bundle.rendered_pages, text = render_pdf(path, outdir)
        bundle.extracted = extract_invoice_fields(text)
        bundle.prompt_injection_hits = prompt_injection_hits(text)
        bundle.events.append(ExecEvent(type="file", name="pdf-render", detail={"pages": len(bundle.rendered_pages)}))
        bundle.sanitized_pdf_path = str(sanitize_pdf(path, outdir))
        (outdir / "bundle-text.txt").write_text(text, encoding="utf-8")
    except (fitz.FileDataError, OSError, ValueError, RuntimeError) as exc:  # corrupted PDFs are evidence, not a crash of the Airlock
        bundle.error = f"pdf-analysis-failed: {exc}"
        bundle.events.append(ExecEvent(type="file", name="pdf-error", detail={"error": str(exc)}))
    return bundle
