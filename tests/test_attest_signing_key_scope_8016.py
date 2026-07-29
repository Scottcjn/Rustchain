"""Issue #8016 — per-miner signing-key scope on /attest/submit.

Reported by @draycolix: ``if sig_hex and pubkey_hex:`` guarded every signature
check with no ``else``, so omitting both fields skipped verification entirely
and the request fell through to nonce validation, hardware binding, fingerprint
validation, auto-enrollment and ticket issuance.

These tests cover BOTH directions, because a fix that only locks things down
would take the vintage fleet offline:

  attacker side
    - cannot attest unsigned for a miner that has a signing key on record
    - cannot present a key that does not derive a canonical RTC identity
    - cannot displace a pinned key on a named identity without signing the
      rotation with the CURRENT key
    - cannot erase a stored signing key with an unsigned submission
    - cannot front-run an epoch enrollment to pin a victim at weight 0
    - cannot rewrite a vintage miner's device_arch

  honest side
    - an unsigned legacy miner with no stored key still attests and still
      earns a non-zero epoch weight
    - a correctly signed RTC-address miner still attests
    - a genuine key rotation signed by the current key still succeeds
"""

import json
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from nacl.signing import SigningKey

integrated_node = sys.modules["integrated_node"]

EPOCH = 85


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

@pytest.fixture
def attest_client(monkeypatch):
    """A Flask test client wired to a fresh on-disk SQLite database.

    An on-disk file (not ``:memory:``) is required because the handler opens
    several independent connections per request.
    """
    tmp_dir = Path(__file__).parent / ".tmp_attest_8016"
    tmp_dir.mkdir(exist_ok=True)
    db_path = tmp_dir / f"{uuid.uuid4().hex}.sqlite3"

    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "HW_BINDING_V2", False, raising=False)
    monkeypatch.setattr(integrated_node, "HW_PROOF_AVAILABLE", False, raising=False)
    monkeypatch.setattr(integrated_node, "HAVE_REPLAY_DEFENSE", False, raising=False)
    monkeypatch.setattr(integrated_node, "_check_hardware_binding",
                        lambda *a, **k: (True, "ok", ""))
    monkeypatch.setattr(integrated_node, "check_ip_rate_limit",
                        lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(integrated_node, "check_challenge_rate_limit",
                        lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(integrated_node, "record_macs", lambda *a, **k: None)
    monkeypatch.setattr(integrated_node, "auto_induct_to_hall", lambda *a, **k: None)
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    monkeypatch.setattr(integrated_node, "slot_to_epoch", lambda slot: EPOCH)
    integrated_node.init_db()

    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as client:
        yield client, db_path

    try:
        db_path.unlink()
    except OSError:
        pass


def _passing_vintage_fingerprint():
    """A fingerprint the server-side validator accepts for a G4.

    For vintage archs ``validate_fingerprint_data`` only strictly requires
    anti_emulation, but the extra checks keep this close to a real payload.
    """
    return {
        "all_passed": True,
        "checks": {
            "anti_emulation": {
                "passed": True,
                "data": {
                    "vm_indicators": [],
                    "paths_checked": ["/proc/cpuinfo"],
                    "dmesg_scanned": True,
                },
            },
            "clock_drift": {"passed": True, "data": {"cv": 0.06, "samples": 80}},
            "simd_identity": {
                "passed": True,
                "data": {"has_altivec": True, "has_sse": False,
                         "has_avx": False, "vec_perm": True},
            },
            "cache_timing": {
                "passed": True,
                "data": {"arch": "powerpc", "l2_l1_ratio": 1.42,
                         "l3_l2_ratio": 1.18},
            },
        },
    }


def _challenge(client, miner):
    resp = client.post("/attest/challenge", json={"miner": miner})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["nonce"]


def _payload(miner, nonce, arch="G4", family="PowerPC"):
    return {
        "miner": miner,
        "miner_id": miner,
        "device": {
            "device_family": family,
            "device_arch": arch,
            "arch": arch,
            "family": family,
            "cores": 2,
            "model": "PowerMac G4",
            "cpu": "PowerPC G4",
            "machine": "ppc",
        },
        "signals": {"hostname": "vintage-host",
                    "macs": ["AA:BB:CC:DD:EE:01"]},
        "report": {"nonce": nonce, "commitment": "commit-" + nonce[:8]},
        "fingerprint": _passing_vintage_fingerprint(),
    }


def _sign(payload, signing_key):
    """Attach a v3 canonical-JSON Ed25519 signature, as the node reconstructs it."""
    body = {k: v for k, v in payload.items()
            if k not in ("signature", "signature_type", "public_key")}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    payload["signature"] = signing_key.sign(canonical).signature.hex()
    payload["public_key"] = signing_key.verify_key.encode().hex()
    payload["signature_type"] = "ed25519"
    return payload


def _rtc_identity(signing_key):
    return integrated_node.address_from_pubkey(
        signing_key.verify_key.encode().hex()
    )


def _stored_key(db_path, miner):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT signing_pubkey FROM miner_attest_recent WHERE miner = ?",
            (miner,),
        ).fetchone()
    return row[0] if row else None


def _stored_arch(db_path, miner):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT device_arch FROM miner_attest_recent WHERE miner = ?",
            (miner,),
        ).fetchone()
    return row[0] if row else None


def _enrolled_weight(db_path, miner, epoch=EPOCH):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT weight FROM epoch_enroll WHERE epoch = ? AND miner_pk = ?",
            (epoch, miner),
        ).fetchone()
    return row[0] if row else None


# --------------------------------------------------------------------------
# honest side — the vintage fleet must keep working
# --------------------------------------------------------------------------

def test_unsigned_legacy_miner_with_no_stored_key_is_accepted(attest_client):
    """A 6502/i386/floppy-class client sends no signature at all.

    It must still attest. This is the case PR #8052 broke.
    """
    client, db_path = attest_client
    miner = "dual-g4-125"
    payload = _payload(miner, _challenge(client, miner))

    resp = client.post("/attest/submit", json=payload)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["ok"] is True


def test_unsigned_legacy_miner_still_earns_nonzero_weight(attest_client):
    """Accepting the attestation is not enough; it must still enroll to earn."""
    client, db_path = attest_client
    miner = "apple2-miner"
    payload = _payload(miner, _challenge(client, miner))

    resp = client.post("/attest/submit", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)

    weight = _enrolled_weight(db_path, miner)
    assert weight is not None, "unsigned legacy miner was not enrolled at all"
    assert weight > 0, f"unsigned legacy miner enrolled at zero weight ({weight})"


def test_unsigned_legacy_miner_can_reattest_repeatedly(attest_client):
    """Successive unsigned attestations must not lock the miner out of itself.

    An unsigned submission stores no key, so the per-miner gate must stay open
    for it rather than pinning something that then rejects the next call.
    """
    client, db_path = attest_client
    miner = "i386-miner"

    for _ in range(3):
        payload = _payload(miner, _challenge(client, miner))
        resp = client.post("/attest/submit", json=payload)
        assert resp.status_code == 200, resp.get_data(as_text=True)

    assert _stored_key(db_path, miner) is None


def test_signed_rtc_address_miner_is_accepted_and_pins_its_key(attest_client):
    """The signing client (rustchain-miner) path still works and pins TOFU."""
    client, db_path = attest_client
    key = SigningKey.generate()
    miner = _rtc_identity(key)
    payload = _sign(_payload(miner, _challenge(client, miner)), key)

    resp = client.post("/attest/submit", json=payload)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _stored_key(db_path, miner) == key.verify_key.encode().hex()


def test_named_identity_pins_key_on_first_signed_attestation(attest_client):
    client, db_path = attest_client
    key = SigningKey.generate()
    miner = "power8-s824-sophia"
    payload = _sign(_payload(miner, _challenge(client, miner)), key)

    resp = client.post("/attest/submit", json=payload)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _stored_key(db_path, miner) == key.verify_key.encode().hex()


def test_authorized_rotation_signed_by_current_key_succeeds(attest_client):
    """A real operator rotating their key can still do so, with proof."""
    client, db_path = attest_client
    old_key = SigningKey.generate()
    new_key = SigningKey.generate()
    miner = "power8-s824-sophia"

    first = _sign(_payload(miner, _challenge(client, miner)), old_key)
    assert client.post("/attest/submit", json=first).status_code == 200

    old_hex = old_key.verify_key.encode().hex()
    new_hex = new_key.verify_key.encode().hex()
    nonce = _challenge(client, miner)
    payload = _payload(miner, nonce)
    payload["rotation_signature"] = old_key.sign(
        integrated_node._attest_rotation_message(miner, old_hex, new_hex, nonce)
    ).signature.hex()
    payload = _sign(payload, new_key)

    resp = client.post("/attest/submit", json=payload)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _stored_key(db_path, miner) == new_hex


# --------------------------------------------------------------------------
# attacker side
# --------------------------------------------------------------------------

def test_unsigned_forgery_rejected_once_miner_has_a_key(attest_client):
    """The core #8016 bypass: unsigned submission naming a keyed victim."""
    client, db_path = attest_client
    victim_key = SigningKey.generate()
    victim = _rtc_identity(victim_key)

    honest = _sign(_payload(victim, _challenge(client, victim)), victim_key)
    assert client.post("/attest/submit", json=honest).status_code == 200

    forged = _payload(victim, _challenge(client, victim), arch="modern",
                      family="x86")

    resp = client.post("/attest/submit", json=forged)

    assert resp.status_code == 401, resp.get_data(as_text=True)
    assert resp.get_json()["code"] == "ATTESTATION_SIGNATURE_REQUIRED"


def test_self_signed_forgery_with_fresh_keypair_rejected_for_rtc_identity(attest_client):
    """Signing with an attacker-generated key must not authorize a victim's
    RTC address. The address derives from the key, so the derivation is checked."""
    client, db_path = attest_client
    victim_key = SigningKey.generate()
    victim = _rtc_identity(victim_key)
    attacker_key = SigningKey.generate()

    forged = _sign(_payload(victim, _challenge(client, victim)), attacker_key)

    resp = client.post("/attest/submit", json=forged)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json()["code"] == "ATTESTATION_KEY_IDENTITY_MISMATCH"


def test_unsigned_rotation_cannot_displace_pinned_key_on_named_identity(attest_client):
    client, db_path = attest_client
    owner_key = SigningKey.generate()
    attacker_key = SigningKey.generate()
    miner = "dual-g4-125"

    first = _sign(_payload(miner, _challenge(client, miner)), owner_key)
    assert client.post("/attest/submit", json=first).status_code == 200

    forged = _sign(_payload(miner, _challenge(client, miner)), attacker_key)

    resp = client.post("/attest/submit", json=forged)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json()["code"] == "ATTESTATION_KEY_ROTATION_UNAUTHORIZED"
    assert _stored_key(db_path, miner) == owner_key.verify_key.encode().hex()


def test_rotation_signed_by_the_wrong_key_is_rejected(attest_client):
    """A rotation proof must come from the CURRENT key, not the new one."""
    client, db_path = attest_client
    owner_key = SigningKey.generate()
    attacker_key = SigningKey.generate()
    miner = "dual-g4-125"

    first = _sign(_payload(miner, _challenge(client, miner)), owner_key)
    assert client.post("/attest/submit", json=first).status_code == 200

    old_hex = owner_key.verify_key.encode().hex()
    new_hex = attacker_key.verify_key.encode().hex()
    nonce = _challenge(client, miner)
    payload = _payload(miner, nonce)
    # Self-signed rotation proof: signed by the attacker's own new key.
    payload["rotation_signature"] = attacker_key.sign(
        integrated_node._attest_rotation_message(miner, old_hex, new_hex, nonce)
    ).signature.hex()
    payload = _sign(payload, attacker_key)

    resp = client.post("/attest/submit", json=payload)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json()["code"] == "ATTESTATION_KEY_ROTATION_UNAUTHORIZED"
    assert _stored_key(db_path, miner) == old_hex


def test_unsigned_submission_cannot_null_a_stored_signing_key(attest_client):
    """Consequence 2 of #8016: erasing the key locked the victim out of the
    hardened signed /epoch/enroll path with a 412."""
    client, db_path = attest_client
    key = SigningKey.generate()
    miner = _rtc_identity(key)

    honest = _sign(_payload(miner, _challenge(client, miner)), key)
    assert client.post("/attest/submit", json=honest).status_code == 200
    assert _stored_key(db_path, miner) == key.verify_key.encode().hex()

    client.post("/attest/submit", json=_payload(miner, _challenge(client, miner)))

    assert _stored_key(db_path, miner) == key.verify_key.encode().hex(), \
        "an unsigned submission erased the stored signing key"


def test_forged_low_weight_enrollment_cannot_front_run_the_victim(attest_client):
    """Consequence 1 of #8016, the actual theft vector.

    epoch_enroll used INSERT OR IGNORE, so a forged fingerprint-FAILING
    attestation submitted first pinned the victim to weight 0 for the whole
    epoch and their honest enrollment was silently ignored.
    """
    client, db_path = attest_client
    miner = "g4-powerbook-115"

    # Attacker moves first with a VM-flagged (weight 0) attestation.
    forged = _payload(miner, _challenge(client, miner))
    forged["fingerprint"] = {
        "all_passed": False,
        "checks": {
            "anti_emulation": {
                "passed": False,
                "data": {"vm_indicators": ["cpuinfo:hypervisor"]},
            },
        },
    }
    assert client.post("/attest/submit", json=forged).status_code == 200
    assert _enrolled_weight(db_path, miner) == 0

    # The rightful owner then attests honestly.
    honest = _payload(miner, _challenge(client, miner))
    assert client.post("/attest/submit", json=honest).status_code == 200

    weight = _enrolled_weight(db_path, miner)
    assert weight > 0, (
        f"honest enrollment was ignored after a forged zero-weight front-run "
        f"(weight={weight})"
    )


def test_high_weight_enrollment_is_not_downgraded_by_a_later_zero(attest_client):
    """The MAX() upsert must keep the anti-downgrade property that
    INSERT OR IGNORE was originally added for."""
    client, db_path = attest_client
    miner = "g4-powerbook-real"

    honest = _payload(miner, _challenge(client, miner))
    assert client.post("/attest/submit", json=honest).status_code == 200
    good_weight = _enrolled_weight(db_path, miner)
    assert good_weight > 0

    forged = _payload(miner, _challenge(client, miner))
    forged["fingerprint"] = {
        "all_passed": False,
        "checks": {"anti_emulation": {"passed": False,
                                      "data": {"vm_indicators": ["qemu"]}}},
    }
    client.post("/attest/submit", json=forged)

    assert _enrolled_weight(db_path, miner) == good_weight, \
        "a later zero-weight attestation downgraded the epoch weight"


def test_unsigned_submission_cannot_rewrite_device_arch(attest_client):
    """Consequence 3 of #8016: rewards read device_arch straight out of
    miner_attest_recent, so an overwrite drops a G4 from 2.5x to 1.0x."""
    client, db_path = attest_client
    miner = "dual-g4-125"

    assert client.post(
        "/attest/submit", json=_payload(miner, _challenge(client, miner))
    ).status_code == 200
    original_arch = _stored_arch(db_path, miner)
    assert original_arch is not None

    downgrade = _payload(miner, _challenge(client, miner),
                         arch="modern", family="x86")
    downgrade["device"]["machine"] = "x86_64"
    client.post("/attest/submit", json=downgrade)

    assert _stored_arch(db_path, miner) == original_arch, \
        "an unsigned submission rewrote the recorded device_arch"


# --------------------------------------------------------------------------
# unit-level checks on the authorization helper itself
# --------------------------------------------------------------------------

def test_rtc_address_shape_only_matches_canonical_form():
    """Legacy suffix wallets (``<hex>RTC``) must NOT be treated as derivable.

    miners/ppc/g5/g5_miner.sh uses ``ppc_g5_130_<md5>RTC`` and cannot sign; if
    that shape were classified as a canonical RTC address the derivation check
    would reject it outright.
    """
    key = SigningKey.generate()
    canonical = integrated_node.address_from_pubkey(
        key.verify_key.encode().hex()
    )

    assert integrated_node._attest_is_rtc_address(canonical) is True
    assert integrated_node._attest_is_rtc_address("ppc_g5_130_abc123RTC") is False
    assert integrated_node._attest_is_rtc_address(
        "eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC") is False
    assert integrated_node._attest_is_rtc_address("dual-g4-125") is False
    assert integrated_node._attest_is_rtc_address("apple2-miner") is False


def test_floppy_miner_rtc_identity_stays_unsigned_capable(attest_client):
    """miners/floppy-miner uses a canonical RTC address AND cannot sign.

    Unsigned must therefore still be accepted for it while no key is pinned,
    which is exactly why the rule keys off "has a stored key", not "looks
    like an RTC address".
    """
    client, db_path = attest_client
    miner = "RTC2fe3c33c77666ff76a1cd0999fd4466ee81250ff"

    resp = client.post("/attest/submit",
                       json=_payload(miner, _challenge(client, miner)))

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _enrolled_weight(db_path, miner) > 0


def test_unsigned_client_allowlist_is_documented():
    """The allowlist is documentation, not a privilege grant."""
    allowlist = integrated_node.UNSIGNED_ATTEST_CLIENT_ALLOWLIST
    assert "miners/apple2/miner6502.c" in allowlist
    assert "miners/i386/miner386.c" in allowlist
    assert "miners/floppy-miner/" in allowlist
    assert "miners/ppc/g5/g5_miner.sh" in allowlist
    assert "miners/rust/src/main.rs" in allowlist
