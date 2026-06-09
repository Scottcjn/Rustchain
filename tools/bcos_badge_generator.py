#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 Badge Generator — Web tool for generating BCOS certification badges.

Generates dynamic SVG badges for BCOS-certified repositories with:
- Tier-based styling (L0/L1/L2)
- Trust score visualization
- Certificate ID embedding
- QR code generation for

# Modified to return HTTP 400 for invalid trust_score and include_qr
def generate_badge(trust_score, include_qr):
    if not isinstance(trust_score, (int, float)) or trust_score < 0 or trust_score > 100:
        return {"error": "Invalid trust score"}, 400
    if not isinstance(include_qr, bool):
        return {"error": "Invalid include_qr"}, 400

    # Rest of the function remains the same