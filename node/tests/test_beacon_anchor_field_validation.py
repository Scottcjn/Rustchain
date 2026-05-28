# SPDX-License-Identifier: MIT

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beacon_anchor import store_envelope, verify_envelope_signature


def _envelope(**overrides):
    envelope = {
        "agent_id": "bcn_test",
        "kind": "hello",
        "nonce": "nonce-1",
        "sig": "00",
        "pubkey": "11",
    }
    envelope.update(overrides)
    return envelope


def test_store_envelope_rejects_structured_required_fields():
    assert store_envelope(_envelope(kind=[])) == {
        "ok": False,
        "error": "invalid_field:kind",
    }
    assert store_envelope(_envelope(nonce={"value": "nonce-1"})) == {
        "ok": False,
        "error": "invalid_field:nonce",
    }


def test_verify_envelope_signature_rejects_structured_signature_fields():
    assert verify_envelope_signature(_envelope(sig=[])) == (
        False,
        "invalid_signature_fields",
    )
    assert verify_envelope_signature(_envelope(pubkey={"hex": "11"})) == (
        False,
        "invalid_signature_fields",
    )
