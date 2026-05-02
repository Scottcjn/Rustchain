#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 PDF Certificate Generator.

Generates Ed25519-signable PDF certificates for BCOS attestations.
Uses fpdf2 (pure Python, no C dependencies).

Usage:
    from bcos_pdf import generate_certificate
    pdf_bytes = generate_certificate(attestation_dict)
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from fpdf import FPDF
except ImportError as e:
    raise ImportError("fpdf2 required: pip install fpdf2") from e


# ── Color palette ─────────────────────────────────────────────────
TIER_COLORS = {
    "L0": (76, 175, 80),  # Green
    "L1": (33, 150, 243),  # Blue
    "L2": (156, 39, 176),  # Purple
}

SCORE_COLORS = {
    "high": (76, 175, 80),  # >= 80
    "medium": (255, 193, 7),  # >= 60
    "low": (244, 67, 54),  # < 60
}

SCORE_WEIGHTS = {
    "license_compliance": ("License Compliance", 20),
    "vulnerability_scan": ("Vulnerability Scan", 25),
    "static_analysis": ("Static Analysis", 20),
    "sbom_completeness": ("SBOM Completeness", 10),
    "dependency_freshness": ("Dependency Freshness", 5),
    "test_evidence": ("Test Evidence", 10),
    "review_attestation": ("Review Attestation", 10),
}


class BCOSCertificatePDF(FPDF):
    """Custom PDF class for BCOS certificates."""

    def header(self):
        # Background color for header
        self.set_fill_color(33, 33, 33)
        self.rect(0, 0, 215.9, 40, "F")

        # Title
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(255, 255, 255)
        self.cell(0, 20, "BCOS ATTESTATION CERTIFICATE", align="C", new_x="LMARGIN", new_y="NEXT")

        # Subtitle
        self.set_font("Helvetica", "", 12)
        self.cell(0, 5, "RustChain Protocol — Verified Relic Hardware", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()} | Cryptographically Signed Attestation", align="C")


def generate_certificate(data: Dict[str, Any]) -> bytes:
    """Generate a PDF certificate from attestation data."""
    pdf = BCOSCertificatePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # 1. Summary Box
    pdf.set_fill_color(245, 245, 245)
    pdf.rect(10, 45, 190, 45, "F")

    pdf.set_y(50)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 10, f"Miner: {data.get('miner_id', 'Unknown')}", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    epoch = data.get("epoch", 0)
    ts = data.get("timestamp", 0)
    dt_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    pdf.cell(0, 5, f"Date: {dt_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"RustChain Epoch: {epoch}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, "Network: RustChain RIP-200 (Proof of Antiquity)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # 2. Hardware Specs
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "HARDWARE SPECIFICATIONS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(40, 7, "Family:", border=0)
    pdf.cell(0, 7, str(data.get("device_family", "N/A")), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(40, 7, "Architecture:", border=0)
    pdf.cell(0, 7, str(data.get("device_arch", "N/A")), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # 3. Score and Tier
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "ATTESTATION SCORES", new_x="LMARGIN", new_y="NEXT")
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # Tier badge
    tier = data.get("tier", "L0")
    tier_color = TIER_COLORS.get(tier, (158, 158, 158))
    pdf.set_fill_color(*tier_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(30, 12, f" TIER {tier} ", align="C", fill=True)

    # Global Score
    score = data.get("score", 0)
    score_cat = "low"
    if score >= 80:
        score_cat = "high"
    elif score >= 60:
        score_cat = "medium"

    pdf.set_fill_color(*SCORE_COLORS[score_cat])
    pdf.set_x(50)
    pdf.cell(40, 12, f" SCORE: {score}/100 ", align="C", fill=True)
    pdf.ln(18)

    # 4. Detailed Breakdown Table
    pdf.set_text_color(33, 33, 33)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(100, 8, "Metric", border=1, fill=True)
    pdf.cell(40, 8, "Weight", border=1, fill=True, align="C")
    pdf.cell(40, 8, "Earned", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    breakdown = data.get("breakdown", {})
    for key, (label, weight) in SCORE_WEIGHTS.items():
        earned = breakdown.get(key, 0)
        pdf.cell(100, 8, label, border=1)
        pdf.cell(40, 8, str(weight), border=1, align="C")
        pdf.cell(40, 8, str(earned), border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(10)

    # 5. Cryptographic Proof
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 10, "CRYPTOGRAPHIC PROOF", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 7)
    pdf.set_text_color(100, 100, 100)
    sig = data.get("signature_hex", "Unsigned")
    pdf.multi_cell(0, 4, f"Signature: {sig}", border=1)

    return pdf.output()


if __name__ == "__main__":
    # Generate a sample certificate for testing
    sample = {
        "miner_id": "RTCtest-miner-123456",
        "epoch": 1234,
        "device_family": "PowerPC",
        "device_arch": "G4",
        "tier": "L1",
        "score": 85,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "breakdown": {
            "license_compliance": 20,
            "vulnerability_scan": 25,
            "static_analysis": 15,
            "sbom_completeness": 10,
            "dependency_freshness": 5,
            "test_evidence": 5,
            "review_attestation": 5,
        },
        "signature_hex": "a" * 128,
    }

    pdf_bytes = generate_certificate(sample)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        print(f"Sample certificate generated at: {tmp.name}")
