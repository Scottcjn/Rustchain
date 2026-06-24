import base64
import importlib.util
import json
import pathlib
import unittest
from tempfile import TemporaryDirectory

try:
    from nacl.signing import SigningKey, VerifyKey
except Exception:  # pragma: no cover - exercised only on minimal legacy hosts
    SigningKey = None
    VerifyKey = None


MODULE_PATH = pathlib.Path(__file__).with_name("rustchain_mac_miner_v2.5.py")


def load_miner_module():
    spec = importlib.util.spec_from_file_location("rustchain_mac_miner_v25", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(SigningKey is None, "PyNaCl unavailable")
class MacMinerSigningTests(unittest.TestCase):
    def test_loads_pkcs8_wallet_file_and_signs_messages(self):
        module = load_miner_module()
        signing_key = SigningKey.generate()
        seed = signing_key.encode()
        public_key_hex = signing_key.verify_key.encode().hex()
        address = module._rtc_address_from_public_key(public_key_hex)
        # Minimal Ed25519 PKCS#8 PrivateKeyInfo wrapper around the raw 32-byte seed.
        pkcs8_der = bytes.fromhex("302e020100300506032b657004220420") + seed

        with TemporaryDirectory() as tmpdir:
            wallet_path = pathlib.Path(tmpdir) / "wallet.json"
            wallet_path.write_text(
                json.dumps(
                    {
                        "address": address,
                        "public_key_hex": public_key_hex,
                        "private_key_pkcs8_der_b64": base64.b64encode(pkcs8_der).decode(),
                    }
                )
            )
            loaded_key, loaded_pubkey, loaded_path = module._load_wallet_signing_key(
                address,
                str(wallet_path),
            )

        message = b"slot:123:miner:test:ts:456"
        signature = loaded_key.sign(message).signature
        VerifyKey(bytes.fromhex(loaded_pubkey)).verify(message, signature)
        self.assertEqual(loaded_pubkey, public_key_hex)
        self.assertTrue(loaded_path.endswith(".json"))

    def test_unreadable_explicit_wallet_file_does_not_fall_back(self):
        module = load_miner_module()

        with TemporaryDirectory() as tmpdir:
            missing_path = pathlib.Path(tmpdir) / "missing-wallet.json"

            with self.assertRaises(OSError):
                module._load_wallet_signing_key("RTC" + "0" * 40, str(missing_path))

    def test_rejects_wallet_file_for_different_configured_address(self):
        module = load_miner_module()
        signing_key = SigningKey.generate()
        public_key_hex = signing_key.verify_key.encode().hex()
        address = module._rtc_address_from_public_key(public_key_hex)

        with TemporaryDirectory() as tmpdir:
            wallet_path = pathlib.Path(tmpdir) / "wallet.json"
            wallet_path.write_text(
                json.dumps(
                    {
                        "address": address,
                        "public_key_hex": public_key_hex,
                        "private_key_hex": signing_key.encode().hex(),
                    }
                )
            )

            with self.assertRaisesRegex(ValueError, "configured wallet address"):
                module._load_wallet_signing_key("RTC" + "0" * 40, str(wallet_path))

    def test_glob_wallet_discovery_requires_address_match(self):
        module = load_miner_module()
        signing_key = SigningKey.generate()
        public_key_hex = signing_key.verify_key.encode().hex()
        address = module._rtc_address_from_public_key(public_key_hex)

        with TemporaryDirectory() as tmpdir:
            wallet_path = pathlib.Path(tmpdir) / "wallet.json"
            wallet_path.write_text(
                json.dumps(
                    {
                        "address": address,
                        "public_key_hex": public_key_hex,
                        "private_key_hex": signing_key.encode().hex(),
                    }
                )
            )
            original_glob = module.glob.glob
            module.glob.glob = lambda pattern: [str(wallet_path)]
            try:
                self.assertEqual(module._find_wallet_file("RTC" + "1" * 40), (None, None))
                loaded_path, loaded_data = module._find_wallet_file(address)
            finally:
                module.glob.glob = original_glob

        self.assertTrue(loaded_path.endswith(".json"))
        self.assertEqual(loaded_data["address"], address)

    def test_signed_attestation_uses_wallet_as_header_key_miner_id(self):
        module = load_miner_module()
        signing_key = SigningKey.generate()
        public_key_hex = signing_key.verify_key.encode().hex()
        address = module._rtc_address_from_public_key(public_key_hex)
        miner = module.MacMiner.__new__(module.MacMiner)
        miner.wallet = address
        miner.miner_id = "m4-local-hardware-id"
        miner.signing_key = signing_key

        self.assertEqual(miner._attestation_miner_id(), address)

    def test_unsigned_attestation_preserves_hardware_miner_id(self):
        module = load_miner_module()
        miner = module.MacMiner.__new__(module.MacMiner)
        miner.wallet = "legacy-wallet"
        miner.miner_id = "m4-local-hardware-id"
        miner.signing_key = None

        self.assertEqual(miner._attestation_miner_id(), "m4-local-hardware-id")


@unittest.skipIf(SigningKey is None, "PyNaCl unavailable")
class AttestationSignMessageTests(unittest.TestCase):
    def test_sign_message_matches_node_pipe_format(self):
        module = load_miner_module()
        msg = module._attestation_sign_message("miner-1", "RTCabc", "nonce-xyz", "commit-hash")
        self.assertEqual(msg, "miner-1|RTCabc|nonce-xyz|commit-hash")

    def test_signature_over_sign_message_verifies(self):
        module = load_miner_module()
        sk = SigningKey.generate()
        msg = module._attestation_sign_message("RTCwallet", "RTCwallet", "n1", "c1")
        sk.verify_key.verify(msg.encode(), sk.sign(msg.encode()).signature)


class ExtractPkcs8Tests(unittest.TestCase):
    def test_rejects_blob_without_ed25519_oid(self):
        module = load_miner_module()
        blob = b"\x30\x10" + b"\x04\x20" + (b"\x11" * 32)
        with self.assertRaises(ValueError):
            module._extract_pkcs8_ed25519_seed(blob)

    def test_accepts_valid_ed25519_pkcs8(self):
        module = load_miner_module()
        seed = b"\x22" * 32
        der = bytes.fromhex("302e020100300506032b657004220420") + seed
        self.assertEqual(module._extract_pkcs8_ed25519_seed(der), seed)


class NodeTransportTLSTests(unittest.TestCase):
    def test_transport_verifies_tls_by_default(self):
        module = load_miner_module()
        calls = []

        class Response:
            status_code = 200

        def fake_get(url, **kwargs):
            calls.append(("get", url, kwargs))
            return Response()

        def fake_post(url, **kwargs):
            calls.append(("post", url, kwargs))
            return Response()

        original_get = module.requests.get
        original_post = module.requests.post
        module.requests.get = fake_get
        module.requests.post = fake_post
        try:
            transport = module.NodeTransport("https://node.example", None)
            transport.get("/health")
            transport.post("/attest", json={})
        finally:
            module.requests.get = original_get
            module.requests.post = original_post

        self.assertEqual(calls[0][2]["verify"], True)
        self.assertEqual(calls[1][2]["verify"], True)
        self.assertEqual(calls[2][2]["verify"], True)

    def test_transport_insecure_tls_is_explicit(self):
        module = load_miner_module()
        calls = []

        class Response:
            status_code = 200

        def fake_get(url, **kwargs):
            calls.append(("get", url, kwargs))
            return Response()

        original_get = module.requests.get
        module.requests.get = fake_get
        try:
            transport = module.NodeTransport("https://node.example", None, insecure_tls=True)
            transport.get("/health")
        finally:
            module.requests.get = original_get

        self.assertEqual(calls[0][2]["verify"], False)
        self.assertEqual(calls[1][2]["verify"], False)


if __name__ == "__main__":
    unittest.main()
