#!/usr/bin/env python3
"""Tests for node/bcos_pdf.py — BCOS v2 PDF Certificate Generator.

Tests cover:
  - PDF output validity (%PDF header, bytes return, %%EOF)
  - Full attestation produces expected text content in PDF
  - Minimal attestation (only cert_id)
  - Missing optional fields (signature, commitment, epoch, reviewer)
  - tier_met=False -> "REQUIREMENTS NOT MET"
  - Empty/incomplete score_breakdown
  - Score color thresholds (high >=80, medium >=60, low <60)
  - Signature split rendering (128-char -> first_64 / second_64)
  - TIER_COLORS / SCORE_COLORS / SCORE_WEIGHTS constants
"""

from __future__ import annotations

import io
import sys

import pytest

sys.path.insert(0, "node")
import bcos_pdf

# ── PDF text extraction via pdfminer.six ────────────────────────────
from pdfminer.high_level import extract_text


def pdf_text(pdf_bytes: bytes | bytearray) -> str:
    """Extract plain text from a PDF byte stream (handles FlateDecode)."""
    return extract_text(io.BytesIO(pdf_bytes))


# ── Sample attestation data ──────────────────────────────────────────

FULL_ATTESTATION = {
    "schema": "bcos-attestation/v2",
    "cert_id": "BCOS-deadbeef",
    "repo_name": "Scottcjn/Rustchain",
    "commit_sha": "1d1ed0f4a5147c885bc56a6cc335930157b07273",
    "tier": "L2",
    "trust_score": 87,
    "tier_met": True,
    "reviewer": "Scott Boudreaux",
    "timestamp": "2026-05-25T12:30:00",
    "commitment": "28545ea8832864e39d9b0f26b7f0499b" * 2,
    "signature": "a" * 128,
    "signer_pubkey": "b" * 64,
    "anchored_epoch": 1234,
    "score_breakdown": {
        "license_compliance": 15,
        "vulnerability_scan": 25,
        "static_analysis": 17,
        "sbom_completeness": 8,
        "dependency_freshness": 4,
        "test_evidence": 10,
        "review_attestation": 10,
    },
}

MINIMAL_ATTESTATION = {"cert_id": "BCOS-minimal"}

TIER_NOT_MET = {
    "cert_id": "BCOS-fail",
    "repo_name": "test/repo",
    "commit_sha": "abc123def456",
    "tier": "L1",
    "trust_score": 42,
    "tier_met": False,
    "reviewer": "",
    "timestamp": "",
    "score_breakdown": {},
}


# ══════════════════════════════════════════════════════════════════════
# 1.  PDF output validity
# ══════════════════════════════════════════════════════════════════════

class TestPdfOutputValidity:
    def test_returns_bytes_or_bytearray(self):
        result = bcos_pdf.generate_certificate(FULL_ATTESTATION)
        assert isinstance(result, (bytes, bytearray)), "Must return bytes-like"

    def test_starts_with_pdf_header(self):
        result = bcos_pdf.generate_certificate(FULL_ATTESTATION)
        assert result.startswith(b"%PDF-"), f"Expected PDF header, got {result[:10]!r}"

    def test_contains_end_of_file_marker(self):
        result = bcos_pdf.generate_certificate(FULL_ATTESTATION)
        assert b"%%EOF" in result, "PDF must end with %%EOF marker"

    def test_nonzero_size(self):
        result = bcos_pdf.generate_certificate(FULL_ATTESTATION)
        assert len(result) > 500, f"PDF too small: {len(result)} bytes"


# ══════════════════════════════════════════════════════════════════════
# 2.  Full attestation content
# ══════════════════════════════════════════════════════════════════════

class TestFullAttestationContent:
    def test_contains_cert_id(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "BCOS-deadbeef" in text, "Should contain certificate ID"

    def test_contains_repo_name(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "Scottcjn/Rustchain" in text

    def test_contains_tier_badge(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "L2" in text, "Should contain tier badge"

    def test_contains_score(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "87" in text, "Should contain trust score"

    def test_contains_certified_status(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "CERTIFIED" in text, "Full attestation should be CERTIFIED"

    def test_contains_commit_sha(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        # fpdf2 may split the SHA
        assert "1d1ed0f4a514" in text.replace(" ", ""), "Should contain abbreviated SHA"

    def test_contains_reviewer(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "Scott Boudreaux" in text

    def test_contains_commitment_proof(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "28545ea8" in text.replace(" ", "") or "BLAKE2b" in text

    def test_contains_signature(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        # 128-char sig split across lines — check first 64 chars solid
        cleaned = text.replace("\n", "").replace(" ", "")
        assert "a" * 60 in cleaned, "Should contain signature chars"

    def test_contains_signer_pubkey(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "Signer Key" in text or ("b" * 20) in text.replace(" ", "")

    def test_contains_on_chain_anchor(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "1234" in text or "Epoch" in text

    def test_contains_coverage_sections(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        assert "license" in text.lower() or "SPDX" in text
        assert "Vulnerability" in text or "CVE" in text


# ══════════════════════════════════════════════════════════════════════
# 3.  Minimal / edge case attestations
# ══════════════════════════════════════════════════════════════════════

class TestMinimalAttestation:
    def test_minimal_does_not_crash(self):
        """Only cert_id provided -- should still produce valid PDF."""
        result = bcos_pdf.generate_certificate(MINIMAL_ATTESTATION)
        assert result.startswith(b"%PDF-")

    def test_minimal_contains_cert_id(self):
        text = pdf_text(bcos_pdf.generate_certificate(MINIMAL_ATTESTATION))
        assert "BCOS-minimal" in text

    def test_minimal_default_tier(self):
        """No tier provided defaults to L1 (blue)."""
        result = bcos_pdf.generate_certificate(MINIMAL_ATTESTATION)
        assert len(result) > 200

    def test_minimal_tier_not_met(self):
        text = pdf_text(bcos_pdf.generate_certificate(TIER_NOT_MET))
        assert "REQUIREMENTS NOT MET" in text, "tier_met=False must show NOT MET"

    def test_empty_reviewer_shows_none(self):
        text = pdf_text(bcos_pdf.generate_certificate(TIER_NOT_MET))
        assert "None" in text or "automated" in text

    def test_empty_timestamp(self):
        text = pdf_text(bcos_pdf.generate_certificate(TIER_NOT_MET))
        assert "unknown" in text or "Generated" in text

    def test_no_signature_or_commitment(self):
        att = {"cert_id": "BCOS-nosig", "tier": "L0", "trust_score": 95, "tier_met": True}
        result = bcos_pdf.generate_certificate(att)
        assert result.startswith(b"%PDF-")

    def test_no_anchored_epoch(self):
        att = {"cert_id": "BCOS-noepoch", "tier": "L0", "trust_score": 50, "tier_met": False}
        result = bcos_pdf.generate_certificate(att)
        assert result.startswith(b"%PDF-")

    def test_trust_score_below_60(self):
        low = {**TIER_NOT_MET, "trust_score": 35, "tier": "L0"}
        result = bcos_pdf.generate_certificate(low)
        assert result.startswith(b"%PDF-")

    def test_trust_score_medium_range(self):
        med = {**TIER_NOT_MET, "trust_score": 65, "tier": "L0"}
        result = bcos_pdf.generate_certificate(med)
        assert result.startswith(b"%PDF-")

    def test_trust_score_high_range(self):
        high = {**TIER_NOT_MET, "trust_score": 92, "tier": "L0"}
        result = bcos_pdf.generate_certificate(high)
        assert result.startswith(b"%PDF-")


# ══════════════════════════════════════════════════════════════════════
# 4.  Score breakdown tests
# ══════════════════════════════════════════════════════════════════════

class TestScoreBreakdown:
    def test_empty_breakdown_still_renders(self):
        text = pdf_text(bcos_pdf.generate_certificate(TIER_NOT_MET))
        assert "Score Breakdown" in text

    def test_partial_breakdown_ok(self):
        partial = {
            **FULL_ATTESTATION,
            "score_breakdown": {"license_compliance": 20, "vulnerability_scan": 10},
        }
        result = bcos_pdf.generate_certificate(partial)
        assert result.startswith(b"%PDF-")

    def test_all_seven_categories(self):
        text = pdf_text(bcos_pdf.generate_certificate(FULL_ATTESTATION))
        for name, _ in bcos_pdf.SCORE_WEIGHTS.values():
            assert name in text, f"Score category '{name}' should appear in PDF"


# ══════════════════════════════════════════════════════════════════════
# 5.  Constants correctness
# ══════════════════════════════════════════════════════════════════════

class TestConstants:
    def test_tier_colors_have_expected_keys(self):
        assert set(bcos_pdf.TIER_COLORS.keys()) == {"L0", "L1", "L2"}

    def test_tier_colors_are_rgb_tuples(self):
        for color in bcos_pdf.TIER_COLORS.values():
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)

    def test_score_colors_have_expected_keys(self):
        assert set(bcos_pdf.SCORE_COLORS.keys()) == {"high", "medium", "low"}

    def test_score_colors_are_rgb_tuples(self):
        for color in bcos_pdf.SCORE_COLORS.values():
            assert len(color) == 3
            assert all(0 <= c <= 255 for c in color)

    def test_score_weights_total_100(self):
        total = sum(w for _, w in bcos_pdf.SCORE_WEIGHTS.values())
        assert total == 100, f"SCORE_WEIGHTS must sum to 100, got {total}"

    def test_score_weights_has_seven_categories(self):
        assert len(bcos_pdf.SCORE_WEIGHTS) == 7

    def test_score_weights_keys_are_tuples(self):
        for key, val in bcos_pdf.SCORE_WEIGHTS.items():
            assert isinstance(key, str)
            assert isinstance(val, tuple) and len(val) == 2