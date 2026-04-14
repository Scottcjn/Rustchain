"""Regression tests for RustChain P2P Phase F — per-peer Ed25519 identity (#2256).

Covers:
- Signature packing / unpacking (legacy hex vs JSON dual bundle)
- Keypair generation + persistence
- Peer registry load + lookup
- Dual-mode signing: legacy HMAC path still works
- Dual-mode signing: Ed25519 path verifies against registered pubkey
- Ed25519 sig verified even when HMAC is absent (ed25519 / strict modes)
- Strict mode rejects HMAC-only messages
- Unknown-peer Ed25519 message rejected
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("RC_P2P_SECRET", "unit-test-secret-0123456789abcdef")

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))


def _reload_modules(signing_mode: str, privkey_path: str, registry_path: str):
    """Re-import p2p_identity + rustchain_p2p_gossip with fresh env.

    Each test uses its own tmpdir for keypair + registry so tests are
    isolated.
    """
    os.environ["RC_P2P_SIGNING_MODE"] = signing_mode
    os.environ["RC_P2P_PRIVKEY_PATH"] = privkey_path
    os.environ["RC_P2P_PEER_REGISTRY"] = registry_path
    # Force-reimport
    for mod in ("p2p_identity", "rustchain_p2p_gossip"):
        if mod in sys.modules:
            del sys.modules[mod]
    import p2p_identity  # noqa: F401
    import rustchain_p2p_gossip  # noqa: F401
    return sys.modules["p2p_identity"], sys.modules["rustchain_p2p_gossip"]


def _make_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE miner_attest_recent "
            "(miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT, "
            "device_arch TEXT, entropy_score INTEGER, fingerprint_passed INTEGER)"
        )
        conn.execute("CREATE TABLE epoch_state (epoch INTEGER, settled INTEGER)")
    return path


def _make_layer(ident, gossip, node_id, peers=None, tmpdir=None):
    db_path = _make_db()
    layer = gossip.GossipLayer(node_id, peers or {}, db_path=db_path)
    layer.broadcast = lambda *args, **kwargs: None
    return layer


# -----------------------------------------------------------------------------
# Unit tests — signature packing
# -----------------------------------------------------------------------------
def test_pack_legacy_hmac_only():
    ident, _ = _reload_modules("hmac", tempfile.mkdtemp() + "/pk.pem",
                               tempfile.mkdtemp() + "/reg.json")
    packed = ident.pack_signature("abc123", None)
    assert packed == "abc123"
    h, e = ident.unpack_signature(packed)
    assert h == "abc123" and e is None


def test_pack_dual_bundle():
    ident, _ = _reload_modules("hmac", tempfile.mkdtemp() + "/pk.pem",
                               tempfile.mkdtemp() + "/reg.json")
    packed = ident.pack_signature("h_hex", "e_hex")
    bundle = json.loads(packed)
    assert bundle == {"h": "h_hex", "e": "e_hex"}
    h, e = ident.unpack_signature(packed)
    assert h == "h_hex" and e == "e_hex"


def test_pack_ed25519_only():
    ident, _ = _reload_modules("hmac", tempfile.mkdtemp() + "/pk.pem",
                               tempfile.mkdtemp() + "/reg.json")
    packed = ident.pack_signature(None, "e_hex")
    assert packed == '{"e":"e_hex"}'
    h, e = ident.unpack_signature(packed)
    assert h is None and e == "e_hex"


# -----------------------------------------------------------------------------
# Unit tests — keypair + registry
# -----------------------------------------------------------------------------
def test_keypair_generation_and_persistence():
    tmpdir = tempfile.mkdtemp()
    path = tmpdir + "/p2p_identity.pem"
    ident, _ = _reload_modules("dual", path, tmpdir + "/reg.json")

    kp1 = ident.LocalKeypair(path)
    pub1 = kp1.pubkey_hex
    assert os.path.exists(path)
    assert len(pub1) == 64  # 32 raw bytes hex

    # Load again from the same file — same pubkey
    kp2 = ident.LocalKeypair(path)
    assert kp2.pubkey_hex == pub1


def test_keypair_file_perms_are_0600():
    tmpdir = tempfile.mkdtemp()
    path = tmpdir + "/p2p_identity.pem"
    ident, _ = _reload_modules("dual", path, tmpdir + "/reg.json")
    ident.LocalKeypair(path)._load_or_generate()
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_peer_registry_load():
    tmpdir = tempfile.mkdtemp()
    reg_path = tmpdir + "/reg.json"
    data = {"version": 1, "peers": [
        {"node_id": "n1", "pubkey_hex": "aa" * 32},
        {"node_id": "n2", "pubkey_hex": "bb" * 32},
    ]}
    with open(reg_path, "w") as f:
        json.dump(data, f)
    ident, _ = _reload_modules("dual", tmpdir + "/pk.pem", reg_path)
    reg = ident.PeerRegistry(reg_path)
    assert len(reg) == 2
    assert reg.get_pubkey("n1") == "aa" * 32
    assert reg.get_pubkey("unknown") is None


# -----------------------------------------------------------------------------
# Integration tests — signing + verification across modes
# -----------------------------------------------------------------------------
def test_dual_mode_hmac_still_works():
    """Dual mode: HMAC signature alone (legacy peer) still verifies."""
    tmpdir = tempfile.mkdtemp()
    ident, gossip = _reload_modules("dual",
                                    tmpdir + "/pk.pem",
                                    tmpdir + "/reg.json")
    layer = _make_layer(ident, gossip, "node1", {})
    # Force HMAC-only signing for this message (simulate legacy peer)
    msg = layer.create_message(gossip.MessageType.PING, {"hello": "world"})
    # In dual mode, signature is a JSON bundle with both — strip to HMAC only
    h, e = ident.unpack_signature(msg.signature)
    assert h is not None
    assert e is not None
    # Replace with HMAC-only (simulating pre-Phase-F peer)
    msg.signature = h
    assert layer.verify_message(msg) is True


def test_dual_mode_ed25519_verifies_against_registered_peer():
    """Dual mode: Ed25519 sig verifies when sender is in registry."""
    tmpdir = tempfile.mkdtemp()
    # Sender setup: generate keypair
    sender_pk_path = tmpdir + "/sender.pem"
    _, _ = _reload_modules("dual", sender_pk_path, tmpdir + "/reg.json")
    from p2p_identity import LocalKeypair
    sender_kp = LocalKeypair(sender_pk_path)
    sender_pubkey = sender_kp.pubkey_hex
    # Build registry containing sender's pubkey under id "node-sender"
    reg_path = tmpdir + "/reg.json"
    with open(reg_path, "w") as f:
        json.dump({"version": 1, "peers": [
            {"node_id": "node-sender", "pubkey_hex": sender_pubkey}
        ]}, f)

    # Re-init both layers with dual mode
    ident, gossip = _reload_modules("dual", sender_pk_path, reg_path)
    sender = _make_layer(ident, gossip, "node-sender", {})
    receiver = _make_layer(ident, gossip, "node-receiver", {"node-sender": "http://x"})

    msg = sender.create_message(gossip.MessageType.PING, {"ping": 1})
    # Msg has both HMAC and Ed25519 in a JSON bundle
    h, e = ident.unpack_signature(msg.signature)
    assert e is not None

    # Receiver verifies — should succeed via Ed25519 path
    assert receiver.verify_message(msg) is True

    # Strip to Ed25519-only (simulating strict-mode peer) — still verifies
    msg.signature = ident.pack_signature(None, e)
    assert receiver.verify_message(msg) is True


def test_strict_mode_rejects_hmac_only():
    """Strict mode: an HMAC-only message is rejected even if HMAC is valid."""
    tmpdir = tempfile.mkdtemp()
    sender_pk = tmpdir + "/sender.pem"
    _, _ = _reload_modules("hmac", sender_pk, tmpdir + "/reg.json")
    # First, produce an HMAC-only message with mode=hmac
    from rustchain_p2p_gossip import GossipLayer as _, MessageType  # noqa: F401
    ident_hmac, gossip_hmac = _reload_modules("hmac", sender_pk, tmpdir + "/reg.json")
    hmac_sender = _make_layer(ident_hmac, gossip_hmac, "node-legacy", {})
    hmac_msg = hmac_sender.create_message(gossip_hmac.MessageType.PING, {"ping": 1})
    assert ident_hmac.unpack_signature(hmac_msg.signature)[1] is None  # no Ed25519

    # Now receiver runs in strict mode with an empty registry
    ident_strict, gossip_strict = _reload_modules("strict",
                                                  tmpdir + "/new_rcvr.pem",
                                                  tmpdir + "/empty.json")
    # Build empty registry file
    with open(tmpdir + "/empty.json", "w") as f:
        json.dump({"version": 1, "peers": []}, f)
    ident_strict, gossip_strict = _reload_modules("strict",
                                                  tmpdir + "/new_rcvr.pem",
                                                  tmpdir + "/empty.json")
    strict_receiver = _make_layer(ident_strict, gossip_strict, "node-strict", {})
    # Message from HMAC-only sender must be rejected
    assert strict_receiver.verify_message(hmac_msg) is False


def test_ed25519_unknown_peer_rejected():
    """Ed25519 signature from an unregistered peer is not accepted."""
    tmpdir = tempfile.mkdtemp()
    sender_pk = tmpdir + "/sender.pem"
    empty_reg = tmpdir + "/empty.json"
    with open(empty_reg, "w") as f:
        json.dump({"version": 1, "peers": []}, f)

    ident, gossip = _reload_modules("dual", sender_pk, empty_reg)
    sender = _make_layer(ident, gossip, "node-unknown", {})
    receiver = _make_layer(ident, gossip, "node-receiver",
                           {"node-unknown": "http://x"})
    msg = sender.create_message(gossip.MessageType.PING, {"ping": 1})
    # Strip HMAC so Ed25519 is the only path
    _, e = ident.unpack_signature(msg.signature)
    msg.signature = ident.pack_signature(None, e)
    # Unknown-peer Ed25519 → verification must fail (no fallback in strict,
    # and dual mode requires registered-peer pubkey for Ed25519 path, falling
    # back to HMAC which we stripped)
    assert receiver.verify_message(msg) is False
