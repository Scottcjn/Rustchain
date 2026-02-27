import os
import sqlite3
import sys
import tempfile
import types
import unittest

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)

mock = types.ModuleType("rustchain_crypto")
class SignedTransaction: pass
class Ed25519Signer: pass
def blake2b256_hex(x): return "00" * 32
def address_from_public_key(b: bytes) -> str: return "addr-from-pub"
mock.SignedTransaction = SignedTransaction
mock.Ed25519Signer = Ed25519Signer
mock.blake2b256_hex = blake2b256_hex
mock.address_from_public_key = address_from_public_key
sys.modules["rustchain_crypto"] = mock

import rustchain_tx_handler as txh

class FakeTx:
    def __init__(self, amount_urtc: int):
        self.from_addr = "addr-from-pub"
        self.to_addr = "addr-target"
        self.amount_urtc = amount_urtc
        self.nonce = 1
        self.timestamp = 1234567890
        self.memo = "poc"
        self.signature = "sig"
        self.public_key = "00"
        self.tx_hash = f"tx-{amount_urtc}"
    def verify(self): return True

class TestNegativeAmountRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.tmp.name
        self.tmp.close()
        self.pool = txh.TransactionPool(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS balances (wallet TEXT PRIMARY KEY, balance_urtc INTEGER NOT NULL, wallet_nonce INTEGER DEFAULT 0)")
            conn.execute("INSERT OR REPLACE INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)", ("addr-from-pub", 1_000_000, 0))
    def tearDown(self):
        try: os.unlink(self.db_path)
        except FileNotFoundError: pass
    def test_negative_amount_rejected(self):
        ok, err = self.pool.validate_transaction(FakeTx(-100))
        self.assertFalse(ok)
        self.assertIn("Invalid amount", err)
    def test_zero_amount_rejected(self):
        ok, err = self.pool.validate_transaction(FakeTx(0))
        self.assertFalse(ok)
        self.assertIn("Invalid amount", err)

if __name__ == "__main__":
    unittest.main()
