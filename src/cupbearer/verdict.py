from __future__ import annotations

from .models import ForensicBundle, TrustBaseline, Verdict, VerdictType


def deterministic_verdict(bundle: ForensicBundle, baseline: TrustBaseline | None = None) -> Verdict:
    reasons: list[str] = []; evidence: list[str] = []
    malicious = False; suspicious = False
    if bundle.canary_hits:
        malicious = True; reasons.append("payload accessed or exfiltrated planted canaries"); evidence.extend(bundle.canary_hits)
    if bundle.network.attempted and bundle.artifact.kind.value in {"script", "skill", "repo"}:
        malicious = True; reasons.append("executable payload attempted network access while offline")
    if bundle.prompt_injection_hits:
        suspicious = True; reasons.append("document contains prompt-injection instructions"); evidence.extend(bundle.prompt_injection_hits)
    if bundle.timed_out:
        suspicious = True; reasons.append("payload did not finish within the detonation timeout")
    if bundle.error:
        suspicious = True; reasons.append("analysis was incomplete: " + bundle.error)
    if baseline:
        fields = bundle.extracted
        if baseline.sender_email and fields.sender_email and baseline.sender_email.lower() != fields.sender_email.lower():
            suspicious = True; reasons.append("sender differs from trust baseline")
        if baseline.bank_account and fields.bank_account and baseline.bank_account != fields.bank_account:
            malicious = True; reasons.append("bank account differs from trusted vendor baseline")
        if baseline.routing_number and fields.routing_number and baseline.routing_number != fields.routing_number:
            malicious = True; reasons.append("bank routing number differs from trusted vendor baseline")
    if malicious:
        return Verdict(verdict=VerdictType.MALICIOUS, confidence=0.95, reasons=reasons, evidence=evidence)
    if suspicious:
        return Verdict(verdict=VerdictType.SUSPICIOUS, confidence=0.72, reasons=reasons or ["anomaly requires owner review"], evidence=evidence)
    if baseline and bundle.extracted.vendor_name and baseline.vendor_name.lower() in bundle.extracted.vendor_name.lower():
        return Verdict(verdict=VerdictType.VERIFIED, confidence=0.86, reasons=["vendor and payment details match trust baseline"], evidence=evidence)
    return Verdict(verdict=VerdictType.INCONCLUSIVE, confidence=0.45, reasons=["no trusted baseline or decisive forensic signal"], evidence=evidence)
