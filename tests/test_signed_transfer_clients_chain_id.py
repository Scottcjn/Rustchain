# SPDX-License-Identifier: MIT
"""Every in-repo signer of POST /wallet/transfer/signed binds chain_id.

Chain binding (chain_id in the request AND in the signed message) is what stops a
signature made on one RustChain network from being replayed on another. Nodes
are moving to *require* it (Scottcjn/Rustchain#8397), so a client that signs
chain-less stops working there.

Each test drives a client's own signing code path, then submits the result to
the real node endpoint with the REAL verifier (no verify_rtc_signature or
address_from_pubkey monkeypatching) and requires:

  * 200 for the untouched request, and
  * rejection when chain_id is stripped from the request (the signed bytes
    include it, so a chain-less reconstruction no longer verifies; nodes with
    #8397 reject it earlier with CHAIN_ID_REQUIRED) or swapped for another
    network's id.

The same file passes against the current node and against #8397's node.
"""

import hashlib
import importlib.util
import json
import random
import shutil
import sqlite3
import subprocess
import sys
import types
import uuid
from pathlib import Path

import httpx  # noqa: F401  real module, imported before any test stubs it
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
SDK_PATH = ROOT / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from rustchain_sdk.client import RustChainClient  # noqa: E402
from rustchain_sdk.wallet import RustChainWallet as SdkWallet  # noqa: E402


def _load(name, path):
    """Import a standalone client module by path (no sys.path side effects)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolve their module via sys.modules
    spec.loader.exec_module(module)
    return module


wallet_signing = _load("rustchain_signed_transfer_under_test",
                       ROOT / "wallet" / "rustchain_signed_transfer.py")

integrated_node = sys.modules["integrated_node"]

NACL_JS = ROOT / "web" / "light-client" / "vendor" / "nacl-fast.min.js"
LIGHT_SIGNING_JS = ROOT / "web" / "light-client" / "signing.js"
NODEJS_BOT_SIGNING_JS = ROOT / "discord-bot-nodejs-v2" / "signing.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")

TO = "RTC" + "b" * 40
OTHER_CHAIN = "rustchain-testnet-v2"


def _key(seed_byte):
    key = Ed25519PrivateKey.from_private_bytes(bytes([seed_byte]) * 32)
    pub = key.public_key().public_bytes_raw()
    return key, pub.hex(), "RTC" + hashlib.sha256(pub).hexdigest()[:40]


def _init_db(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER NOT NULL);
            CREATE TABLE pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL, from_miner TEXT NOT NULL, to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL, reason TEXT, status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL, confirms_at INTEGER NOT NULL, tx_hash TEXT,
                voided_by TEXT, voided_reason TEXT, confirmed_at INTEGER
            );
            CREATE TABLE transfer_nonces (
                from_address TEXT NOT NULL, nonce TEXT NOT NULL, used_at INTEGER NOT NULL,
                PRIMARY KEY (from_address, nonce)
            );
            CREATE UNIQUE INDEX idx_pending_ledger_tx_hash ON pending_ledger(tx_hash);
            """
        )


@pytest.fixture
def node(monkeypatch, tmp_path):
    """The node app with its real signature verification."""
    db_path = tmp_path / f"{uuid.uuid4().hex}.sqlite3"
    _init_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "current_slot", lambda: 12345)
    integrated_node.app.config["TESTING"] = True

    class Node:
        chain_id = integrated_node.CHAIN_ID
        client = integrated_node.app.test_client()

        def fund(self, address, rtc=100):
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO balances (miner_id, amount_i64) VALUES (?, ?)",
                    (address, int(rtc * 1_000_000)),
                )

        def post(self, body):
            return self.client.post("/wallet/transfer/signed", json=body)

        def assert_chain_bound_and_accepted(self, body):
            """Tampered chain_id must fail; the untouched request must land."""
            assert body.get("chain_id") == self.chain_id, body
            stripped = {k: v for k, v in body.items() if k != "chain_id"}
            r = self.post(stripped)
            assert r.status_code in (400, 401), (r.status_code, r.get_json())
            assert r.status_code != 200
            swapped = dict(body, chain_id=OTHER_CHAIN)
            r = self.post(swapped)
            assert r.status_code == 400, r.get_json()
            assert "chain_id" in json.dumps(r.get_json())
            r = self.post(body)
            assert r.status_code == 200, r.get_json()
            assert r.get_json()["ok"] is True

    yield Node()


def _node_messages(frm, to, amount, memo, nonce, chain_id, fee=0.0):
    return integrated_node._wallet_transfer_signed_messages(
        frm, to, float(amount), float(fee), memo, str(nonce), chain_id
    )


def _run_node_js(script):
    out = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, timeout=60, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# --------------------------------------------------------------------------
# web/light-client (browser) — signing.js + vendored tweetnacl
# --------------------------------------------------------------------------

def _js_signed_body(module_path, seed, amount, memo, nonce, chain_id, light):
    call = (
        "s.buildSignedTransfer(nacl, {secretKey: kp.secretKey, publicKey: kp.publicKey, "
        "fromAddress: addr, toAddress: TO, amountRtc: AMT, memo: MEMO, nonce: NONCE, chainId: CHAIN})"
        if light
        else "s.buildSignedTransfer(nacl, {secretKey: kp.secretKey, toAddress: TO, "
        "amountRtc: AMT, memo: MEMO, nonce: NONCE, chainId: CHAIN})"
    )
    script = f"""
const nacl = require({json.dumps(str(NACL_JS))});
const s = require({json.dumps(str(module_path))});
const kp = nacl.sign.keyPair.fromSeed(new Uint8Array(32).fill({seed}));
const addr = "RTC" + require("crypto").createHash("sha256")
  .update(Buffer.from(kp.publicKey)).digest("hex").slice(0, 40);
const TO = {json.dumps(TO)}, AMT = {json.dumps(amount)}, MEMO = {json.dumps(memo)};
const NONCE = {nonce}, CHAIN = {json.dumps(chain_id)};
console.log(JSON.stringify({call}));
"""
    return _run_node_js(script)


@needs_node
@pytest.mark.parametrize("amount", [1.5, 2.0, 0.00005])
def test_light_client_signs_chain_bound_transfer(node, amount):
    _, pub, addr = _key(11)
    node.fund(addr)
    out = _js_signed_body(LIGHT_SIGNING_JS, 11, amount, "light", 1733420000001, node.chain_id, True)
    assert out["body"]["public_key"] == pub
    _, legacy = _node_messages(addr, TO, amount, "light", 1733420000001, node.chain_id)
    assert out["message"].encode() == legacy
    node.assert_chain_bound_and_accepted(out["body"])


@needs_node
def test_nodejs_discord_bot_signs_chain_bound_transfer(node):
    _, pub, addr = _key(12)
    node.fund(addr)
    out = _js_signed_body(NODEJS_BOT_SIGNING_JS, 12, 3.25, "tip", 1733420000002, node.chain_id, False)
    assert out["body"]["from_address"] == addr
    assert out["body"]["public_key"] == pub
    node.assert_chain_bound_and_accepted(out["body"])


@needs_node
@pytest.mark.parametrize("module_path", [LIGHT_SIGNING_JS, NODEJS_BOT_SIGNING_JS])
def test_js_amount_encoding_matches_python_json(module_path):
    """JS must print floats exactly as the node's json.dumps does."""
    rng = random.Random(8397)
    values = [1.0, 1.5, 0.1, 0.000001, 0.00005, 0.0001, 0.000249, 123456.789,
              1e15, 1e16, 1.5e16, 8388608.0, 0.3, 2.675]
    values += [rng.randint(1, 10**9) / 10**rng.randint(0, 6) for _ in range(300)]
    values += [rng.random() * 10**rng.randint(-7, 17) for _ in range(300)]
    script = f"""
const s = require({json.dumps(str(module_path))});
console.log(JSON.stringify({json.dumps(values)}.map(s.pyJsonNumber)));
"""
    assert _run_node_js(script) == [json.dumps(v) for v in values]


@needs_node
def test_js_signers_refuse_invalid_chain_id():
    for module_path in (LIGHT_SIGNING_JS, NODEJS_BOT_SIGNING_JS):
        script = f"""
const s = require({json.dumps(str(module_path))});
const bad = [undefined, "", "has space", "x".repeat(65)];
console.log(JSON.stringify(bad.map(c => {{
  try {{ s.canonicalSignedMessage("RTCa", "RTCb", 1, "", "1", c); return "signed"; }}
  catch (e) {{ return e.message; }}
}})));
"""
        assert _run_node_js(script) == ["invalid_chain_id"] * 4


# --------------------------------------------------------------------------
# wallet/rustchain_wallet_secure.py — via wallet/rustchain_signed_transfer.py
# --------------------------------------------------------------------------

class _CryptoWallet:
    """rustchain_crypto.RustChainWallet signing API (address, public_key, sign_message)."""

    def __init__(self, seed_byte):
        self._key, self.public_key, self.address = _key(seed_byte)

    def sign_message(self, message: bytes) -> str:
        return self._key.sign(message).hex()


def test_secure_wallet_signs_chain_bound_transfer(node):
    wallet = _CryptoWallet(13)
    node.fund(wallet.address)
    chain_id = wallet_signing.chain_id_from_network_info(
        node.client.get("/network/info").get_json()
    )
    body = wallet_signing.build_signed_transfer(
        wallet, TO, 4.5, "secure", chain_id, nonce=1733420000003
    )
    node.assert_chain_bound_and_accepted(body)


def test_secure_wallet_refuses_missing_chain_id():
    with pytest.raises(ValueError):
        wallet_signing.chain_id_from_network_info({"network": "mainnet"})
    with pytest.raises(ValueError):
        wallet_signing.build_signed_transfer(_CryptoWallet(13), TO, 1, "", "", nonce=1)


def test_secure_wallet_gui_uses_chain_bound_builder():
    src = (ROOT / "wallet" / "rustchain_wallet_secure.py").read_text()
    assert "build_signed_transfer(verified_wallet" in src
    assert "/network/info" in src
    assert "verified_wallet.sign_transaction(" not in src


# --------------------------------------------------------------------------
# integrations/telegram-tip-bot/bot.py
# --------------------------------------------------------------------------

def _load_telegram_bot(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("BOT_SECRET", "test-secret")
    monkeypatch.delenv("RUSTCHAIN_CHAIN_ID", raising=False)
    telegram = types.ModuleType("telegram")
    telegram.Update = telegram.BotCommand = object
    ext = types.ModuleType("telegram.ext")
    ext.Application = ext.CommandHandler = object
    ext.ContextTypes = types.SimpleNamespace(DEFAULT_TYPE=object)
    monkeypatch.setitem(sys.modules, "telegram", telegram)
    monkeypatch.setitem(sys.modules, "telegram.ext", ext)
    path = ROOT / "integrations" / "telegram-tip-bot" / "bot.py"
    spec = importlib.util.spec_from_file_location("rustchain_telegram_tip_bot", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_telegram_bot_signs_chain_bound_transfer(node, monkeypatch, tmp_path):
    bot = _load_telegram_bot(monkeypatch, tmp_path)
    priv, pub, addr = bot.derive_keypair(42, "test-secret")
    node.fund(addr)
    seen = {}
    # Route the bot's HTTP helpers to the node app: chain_id comes from the
    # node's own /network/info, and the transfer body is what the bot sends.
    monkeypatch.setattr(bot, "api_get", lambda ep, params=None: node.client.get(ep).get_json())
    monkeypatch.setattr(bot, "api_post", lambda ep, data: seen.setdefault(ep, data))
    bot.send_signed_transfer(addr, TO, 1.25, priv, pub, memo="tg")
    node.assert_chain_bound_and_accepted(seen["/wallet/transfer/signed"])


def test_telegram_bot_refuses_to_sign_without_chain_id(monkeypatch, tmp_path):
    bot = _load_telegram_bot(monkeypatch, tmp_path)
    priv, pub, addr = bot.derive_keypair(42, "test-secret")
    posted = []
    monkeypatch.setattr(bot, "api_get", lambda ep, params=None: {"error": "down"})
    monkeypatch.setattr(bot, "api_post", lambda ep, data: posted.append(data))
    result = bot.send_signed_transfer(addr, TO, 1.0, priv, pub)
    assert "chain_id" in result["error"]
    assert posted == []


# --------------------------------------------------------------------------
# tools/discord-bot/bot.py — /tip instructions (the bot holds no keys)
# --------------------------------------------------------------------------

def _load_python_discord_bot(monkeypatch):
    class _Bot:
        def __init__(self, *a, **k):
            self.tree = types.SimpleNamespace(command=lambda *a, **k: (lambda f: f))

    app_commands = types.SimpleNamespace(describe=lambda **k: (lambda f: f))
    monkeypatch.setitem(sys.modules, "discord", types.SimpleNamespace(
        app_commands=app_commands, Interaction=object,
        Intents=types.SimpleNamespace(default=lambda: types.SimpleNamespace()),
    ))
    monkeypatch.setitem(sys.modules, "discord.ext", types.SimpleNamespace(
        commands=types.SimpleNamespace(Bot=_Bot)))
    monkeypatch.setitem(sys.modules, "discord.ext.commands", types.SimpleNamespace(Bot=_Bot))
    monkeypatch.setitem(sys.modules, "discord.app_commands", app_commands)
    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(
        AsyncClient=lambda *a, **k: None, Timeout=lambda *a, **k: None))
    path = ROOT / "tools" / "discord-bot" / "bot.py"
    spec = importlib.util.spec_from_file_location("rustchain_discord_bot_chain_id", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_discord_bot_tip_template_is_chain_bound(node, monkeypatch):
    bot = _load_python_discord_bot(monkeypatch)
    key, pub, addr = _key(14)
    node.fund(addr)
    template = bot.signed_transfer_template(TO, 2.5, node.chain_id)
    nonce = 1733420000004
    # Following the instructions literally must produce a request the node accepts.
    message = template["message"].replace("<your RTC address>", addr).replace("<nonce>", str(nonce))
    _, legacy = _node_messages(addr, TO, 2.5, "", nonce, node.chain_id)
    assert message.encode() == legacy
    body = dict(template["body"], from_address=addr, nonce=nonce, public_key=pub,
                signature=key.sign(message.encode()).hex())
    node.assert_chain_bound_and_accepted(body)


# --------------------------------------------------------------------------
# sdk/python — RustChainClient.wallet_transfer_with_wallet
# --------------------------------------------------------------------------

def test_python_sdk_wallet_transfer_binds_node_chain_id(node, monkeypatch):
    import asyncio

    wallet = SdkWallet.create(strength=128)
    node.fund(wallet.address)
    client = RustChainClient()
    sent = {}

    async def network_info():
        return node.client.get("/network/info").get_json()

    async def post_object(path, params=None, json_data=None):
        sent["body"] = json_data
        return {"ok": True}

    monkeypatch.setattr(client, "network_info", network_info)
    monkeypatch.setattr(client, "_post_object", post_object)
    asyncio.run(client.wallet_transfer_with_wallet(wallet, TO, 1.75, memo="sdk"))
    node.assert_chain_bound_and_accepted(sent["body"])


# --------------------------------------------------------------------------
# rustchain-wallet (Rust) — golden vector from its unit tests
# (rustchain-wallet/src/transaction.rs, test_chain_bound_signature_matches_node_golden_vector)
# --------------------------------------------------------------------------

RUST_GOLDEN = {
    "from": "RTCfe812c12f3ab4ce6ac5db69ac352f906cb1b11ef",
    "public_key": "ea4a6c63e29c520abef5507b132ec5f9954776aebebe7b92421eea691446d22c",
    "message": '{"amount":1.5,"chain_id":"rustchain-mainnet-v2","from":"RTCfe812c12f3ab4ce6ac5db69ac352f906cb1b11ef","memo":"rust golden","nonce":"1733420000123","to":"RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}',
    "signature": "f7df488d1ffe61d28b35437b62771c2425d47d1ef1b3169292f731e69b639bf8c63f6b2cdc85a80114d60d50eac9421a04f7970ea593d0e5cc063d5e6565190d",
}


def test_rust_wallet_golden_vector_verifies_on_node(node, monkeypatch):
    monkeypatch.setattr(integrated_node, "CHAIN_ID", "rustchain-mainnet-v2")
    node.chain_id = "rustchain-mainnet-v2"
    _, legacy = _node_messages(RUST_GOLDEN["from"], TO, 1.5, "rust golden",
                               1733420000123, "rustchain-mainnet-v2")
    assert legacy == RUST_GOLDEN["message"].encode()
    node.fund(RUST_GOLDEN["from"])
    # Body as rustchain-wallet/src/client.rs::signed_transfer_payload builds it.
    node.assert_chain_bound_and_accepted({
        "from_address": RUST_GOLDEN["from"],
        "to_address": TO,
        "amount_rtc": 1.5,
        "nonce": "1733420000123",
        "memo": "rust golden",
        "signature": RUST_GOLDEN["signature"],
        "public_key": RUST_GOLDEN["public_key"],
        "chain_id": "rustchain-mainnet-v2",
    })


# --------------------------------------------------------------------------
# Signers that already bound chain_id: keep them honest.
# --------------------------------------------------------------------------

def test_wallet_cli_signs_chain_bound_transfer(node):
    cli = _load("rustchain_wallet_cli_chain_id", ROOT / "tools" / "rustchain_wallet_cli.py")
    _, _, addr = _key(15)
    node.fund(addr)
    body = cli._sign_transfer((bytes([15]) * 32).hex(), addr, TO, 1.0, "cli",
                              1733420000005, chain_id=node.chain_id)
    node.assert_chain_bound_and_accepted(body)


def test_a2a_transfer_signs_chain_bound_transfer(node):
    a2a_transfer = _load("a2a_transfer_under_test", ROOT / "tools" / "a2a_transfer" / "a2a_transfer.py")
    signer = a2a_transfer.Ed25519Signer.from_hex((bytes([16]) * 32).hex())
    node.fund(signer.address)
    body = a2a_transfer.build_payload(signer, TO, 1.0, 1733420000006, memo="a2a",
                                      chain_id=node.chain_id)
    node.assert_chain_bound_and_accepted(body)


def _secure_wallet_gui(monkeypatch, tmp_path, crypto_wallet, fetch):
    """SecureFounderWallet.send_signed_payment with Tk widgets/dialogs stubbed."""
    pytest.importorskip("_tkinter", reason="tkinter not available")
    from unittest.mock import MagicMock

    monkeypatch.syspath_prepend(str(ROOT / "wallet"))
    gui = _load("rustchain_wallet_secure_under_test", ROOT / "wallet" / "rustchain_wallet_secure.py")
    (tmp_path / "w.json").write_text("{}")
    monkeypatch.setattr(gui, "KEYSTORE_DIR", tmp_path)
    monkeypatch.setattr(gui, "messagebox", MagicMock(askyesno=lambda *a: True))
    monkeypatch.setattr(gui.RustChainWallet, "from_encrypted",
                        classmethod(lambda cls, enc, pw: crypto_wallet))

    def entry(value):
        return MagicMock(get=lambda: value)

    app = MagicMock(spec=gui.SecureFounderWallet)
    app.wallet = crypto_wallet
    app.wallet_name = entry("w")
    app.recipient_entry, app.amount_entry = entry(TO), entry("2.0")
    app.memo_entry, app.password_entry = entry("gui"), entry("pw")
    app.sig_label, app.status_var, app.tx_tree = MagicMock(), MagicMock(), MagicMock()
    app._fetch_with_retry = fetch
    return gui.SecureFounderWallet.send_signed_payment.__get__(app)


def test_secure_wallet_gui_send_is_chain_bound_and_reports_success(node, monkeypatch, tmp_path):
    wallet = _CryptoWallet(17)
    node.fund(wallet.address)
    sent = []

    def fetch(url, method="GET", data=None, **_):
        path = url.split("://", 1)[-1].split("/", 1)[1]
        if method == "POST":
            sent.append(data)
            return node.post(data).get_json(), None
        return node.client.get("/" + path).get_json(), None

    assert _secure_wallet_gui(monkeypatch, tmp_path, wallet, fetch)() is True
    assert sent[0]["chain_id"] == node.chain_id


def test_secure_wallet_gui_send_fails_explicitly_without_chain_id(monkeypatch, tmp_path):
    posted = []

    def fetch(url, method="GET", data=None, **_):
        if method == "POST":
            posted.append(data)
        return {"network": "mainnet"}, None  # no chain_id

    assert _secure_wallet_gui(monkeypatch, tmp_path, _CryptoWallet(18), fetch)() is False
    assert posted == []


# --------------------------------------------------------------------------
# Non-ASCII memos. The node signs json.dumps(...) with ensure_ascii=True: every
# UTF-16 code unit outside 0x20-0x7e (DEL, accents, emoji as a surrogate pair)
# becomes lowercase \uxxxx. Raw UTF-8 in the signed bytes fails verification.
# --------------------------------------------------------------------------

UNICODE_MEMO = "caf\u00e9 \u2615 \U0001F600 \x7f \n"
UNICODE_MEMO_JSON = r'"caf\u00e9 \u2615 \ud83d\ude00 \u007f \n"'


def test_unicode_memo_golden_matches_node_encoding():
    assert json.dumps(UNICODE_MEMO) == UNICODE_MEMO_JSON


@needs_node
@pytest.mark.parametrize("module_path,light,seed", [
    (LIGHT_SIGNING_JS, True, 31), (NODEJS_BOT_SIGNING_JS, False, 32)])
def test_js_signers_unicode_memo_verifies_on_node(node, module_path, light, seed):
    _, _, addr = _key(seed)
    node.fund(addr)
    out = _js_signed_body(module_path, seed, 1.5, UNICODE_MEMO, 1733420000031, node.chain_id, light)
    assert UNICODE_MEMO_JSON in out["message"]
    _, legacy = _node_messages(addr, TO, 1.5, UNICODE_MEMO, 1733420000031, node.chain_id)
    assert out["message"].encode() == legacy
    assert out["body"]["memo"] == UNICODE_MEMO  # raw memo in the request; node re-encodes
    node.assert_chain_bound_and_accepted(out["body"])


@needs_node
@pytest.mark.parametrize("module_path", [LIGHT_SIGNING_JS, NODEJS_BOT_SIGNING_JS])
def test_js_string_encoding_matches_python_json(module_path):
    rng = random.Random(8533)
    alphabet = ([chr(c) for c in range(0x00, 0x100)]
                + ["\u2028", "\u2029", "\ufeff", "\uffff", "\u2615", "\U0001F600", "\U0010FFFF"])
    values = [UNICODE_MEMO, "", '"\\/', "".join(chr(c) for c in range(0x20))]
    values += ["".join(rng.choice(alphabet) for _ in range(rng.randint(1, 24))) for _ in range(400)]
    script = f"""
const s = require({json.dumps(str(module_path))});
const vals = JSON.parse(require("fs").readFileSync(0, "utf8"));
console.log(JSON.stringify(vals.map(s.pyJsonString)));
"""
    out = subprocess.run(["node", "-e", script], input=json.dumps(values), capture_output=True,
                         text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout) == [json.dumps(v) for v in values]


@pytest.mark.parametrize("seed", [33])
def test_python_signers_unicode_memo_verify_on_node(node, monkeypatch, tmp_path, seed):
    """Secure-wallet helper, Telegram bot, wallet CLI, a2a: json.dumps defaults."""
    wallet = _CryptoWallet(seed)
    node.fund(wallet.address)
    node.assert_chain_bound_and_accepted(wallet_signing.build_signed_transfer(
        wallet, TO, 1.0, UNICODE_MEMO, node.chain_id, nonce=1733420000033))

    bot = _load_telegram_bot(monkeypatch, tmp_path)
    priv, pub, addr = bot.derive_keypair(77, "test-secret")
    node.fund(addr)
    seen = {}
    monkeypatch.setattr(bot, "api_get", lambda ep, params=None: node.client.get(ep).get_json())
    monkeypatch.setattr(bot, "api_post", lambda ep, data: seen.setdefault(ep, data))
    bot.send_signed_transfer(addr, TO, 1.0, priv, pub, memo=UNICODE_MEMO)
    node.assert_chain_bound_and_accepted(seen["/wallet/transfer/signed"])

    cli = _load("rustchain_wallet_cli_unicode", ROOT / "tools" / "rustchain_wallet_cli.py")
    _, _, cli_addr = _key(34)
    node.fund(cli_addr)
    node.assert_chain_bound_and_accepted(cli._sign_transfer(
        (bytes([34]) * 32).hex(), cli_addr, TO, 1.0, UNICODE_MEMO, 1733420000034,
        chain_id=node.chain_id))

    a2a = _load("a2a_transfer_unicode", ROOT / "tools" / "a2a_transfer" / "a2a_transfer.py")
    signer = a2a.Ed25519Signer.from_hex((bytes([35]) * 32).hex())
    node.fund(signer.address)
    node.assert_chain_bound_and_accepted(a2a.build_payload(
        signer, TO, 1.0, 1733420000035, memo=UNICODE_MEMO, chain_id=node.chain_id))


RUST_UNICODE_GOLDEN = {
    # rustchain-wallet/src/transaction.rs,
    # test_non_ascii_memo_matches_python_ensure_ascii_golden_vector
    "message": '{"amount":1.5,"chain_id":"rustchain-mainnet-v2","from":"RTCfe812c12f3ab4ce6ac5db69ac352f906cb1b11ef","memo":"caf\\u00e9 \\u2615 \\ud83d\\ude00 \\u007f \\n","nonce":"1733420000124","to":"RTCbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}',
    "signature": "c6761c58404ae8fc4de8ed30eb65d328ec8a08db075addf3b92713fa7b5cd837ae2d09f5b819f28ce85a42941d5db012fd0ae5777e924e765a77b6bdae5ea400",
}


def test_rust_wallet_unicode_golden_vector_verifies_on_node(node, monkeypatch):
    monkeypatch.setattr(integrated_node, "CHAIN_ID", "rustchain-mainnet-v2")
    node.chain_id = "rustchain-mainnet-v2"
    _, legacy = _node_messages(RUST_GOLDEN["from"], TO, 1.5, UNICODE_MEMO,
                               1733420000124, "rustchain-mainnet-v2")
    assert legacy == RUST_UNICODE_GOLDEN["message"].encode()
    node.fund(RUST_GOLDEN["from"])
    node.assert_chain_bound_and_accepted({
        "from_address": RUST_GOLDEN["from"], "to_address": TO, "amount_rtc": 1.5,
        "nonce": "1733420000124", "memo": UNICODE_MEMO,
        "signature": RUST_UNICODE_GOLDEN["signature"],
        "public_key": RUST_GOLDEN["public_key"], "chain_id": "rustchain-mainnet-v2",
    })


# --------------------------------------------------------------------------
# Fail closed on chain_id; validate its shape everywhere.
# --------------------------------------------------------------------------

class _FakeApi:
    def __init__(self, info):
        self.info = info

    async def network_info(self):
        return self.info


@pytest.mark.parametrize("override,info,expected", [
    ("", None, None),                                        # node unreachable
    ("", {"network": "mainnet"}, None),                      # no chain_id
    ("", {"chain_id": "bad id"}, None),                      # malformed
    ("", {"chain_id": "rustchain-testnet-v2"}, "rustchain-testnet-v2"),
    ("rustchain-mainnet-v2", None, "rustchain-mainnet-v2"),  # explicit override
    ("bad id", {"chain_id": "rustchain-mainnet-v2"}, None),  # malformed override
])
def test_python_discord_bot_chain_id_fails_closed(monkeypatch, override, info, expected):
    import asyncio

    bot = _load_python_discord_bot(monkeypatch)
    monkeypatch.setattr(bot, "CHAIN_ID_OVERRIDE", override)
    assert asyncio.run(bot.resolve_chain_id(_FakeApi(info))) == expected


def test_python_discord_bot_tip_refuses_without_chain_id(monkeypatch):
    import asyncio

    bot = _load_python_discord_bot(monkeypatch)
    monkeypatch.setattr(bot, "CHAIN_ID_OVERRIDE", "")
    monkeypatch.setattr(bot, "bot", types.SimpleNamespace(api=_FakeApi(None)), raising=False)
    sent = []

    async def defer(**_):
        return None

    async def send(*args, **kwargs):
        sent.append((args, kwargs))

    interaction = types.SimpleNamespace(
        response=types.SimpleNamespace(defer=defer),
        followup=types.SimpleNamespace(send=send))
    asyncio.run(bot.cmd_tip(interaction, "RTC" + "c" * 40, 1.0))
    assert len(sent) == 1
    assert "chain_id" in sent[0][0][0] and "embed" not in sent[0][1]


@pytest.mark.parametrize("nonce", ["001", "5", 1.5, True, 0, -3, None.__class__])
def test_secure_wallet_helper_rejects_bad_nonce(nonce):
    with pytest.raises((TypeError, ValueError)):
        wallet_signing.build_signed_transfer(_CryptoWallet(13), TO, 1.0, "", "rustchain-mainnet-v2",
                                             nonce=nonce)


@pytest.mark.parametrize("chain_id", [None, "", "bad id", "x" * 65])
def test_a2a_build_payload_requires_chain_id(chain_id):
    a2a = _load("a2a_transfer_chain_required", ROOT / "tools" / "a2a_transfer" / "a2a_transfer.py")
    signer = a2a.Ed25519Signer.from_hex((bytes([16]) * 32).hex())
    with pytest.raises(a2a.A2AError, match="chain_id"):
        a2a.build_payload(signer, TO, 1.0, 1733420000006, chain_id=chain_id)


# --------------------------------------------------------------------------
# Stale cached chain_id: on "chain_id does not match active network" the client
# refetches once and re-signs (the node never recorded the rejected nonce).
# --------------------------------------------------------------------------

STALE_CHAIN = "rustchain-old-network"


def test_telegram_bot_refetches_stale_chain_id_once(node, monkeypatch, tmp_path):
    bot = _load_telegram_bot(monkeypatch, tmp_path)
    priv, pub, addr = bot.derive_keypair(43, "test-secret")
    node.fund(addr)
    monkeypatch.setattr(bot, "_chain_id_cache", STALE_CHAIN)
    monkeypatch.setattr(bot, "api_get", lambda ep, params=None: node.client.get(ep).get_json())
    posted = []

    class _Resp:  # requests.Response shape, backed by the node app
        def __init__(self, r):
            self.status_code, self.ok, self._json = r.status_code, r.status_code < 400, r.get_json()

        def json(self):
            return self._json

    def post(url, json=None, **_):
        posted.append(json["chain_id"])
        return _Resp(node.post(json))

    monkeypatch.setattr(bot.requests, "post", post)
    result = bot.send_signed_transfer(addr, TO, 1.0, priv, pub, memo="stale")
    assert result.get("ok") is True, result
    assert posted == [STALE_CHAIN, node.chain_id]


def test_telegram_bot_api_post_keeps_node_error_body(node, monkeypatch, tmp_path):
    bot = _load_telegram_bot(monkeypatch, tmp_path)

    class _Resp:
        status_code, ok = 400, False

        def json(self):
            return {"error": "chain_id does not match active network", "expected_chain_id": "x"}

    monkeypatch.setattr(bot.requests, "post", lambda *a, **k: _Resp())
    result = bot.api_post("/wallet/transfer/signed", {})
    assert result["error"].startswith("chain_id does not match")
    assert result["http_status"] == 400


def _sdk_client_on_node(node, posted):
    """RustChainClient whose real HTTP layer (_get/_post) talks to the node app."""
    def handler(request):
        if request.method == "GET":
            r = node.client.get(request.url.path)
        else:
            body = json.loads(request.content)
            posted.append(body["chain_id"])
            r = node.post(body)
        return httpx.Response(r.status_code, json=r.get_json())

    client = RustChainClient()
    client._client = httpx.AsyncClient(base_url="https://node.test",
                                       transport=httpx.MockTransport(handler))
    return client


def test_python_sdk_refetches_stale_chain_id_once(node):
    import asyncio

    wallet = SdkWallet.create(strength=128)
    node.fund(wallet.address)
    posted = []

    async def run():
        async with _sdk_client_on_node(node, posted) as client:
            client._chain_id = STALE_CHAIN
            return await client.wallet_transfer_with_wallet(wallet, TO, 1.0, memo="sdk")

    assert asyncio.run(run())["ok"] is True
    assert posted == [STALE_CHAIN, node.chain_id]


def test_python_sdk_explicit_chain_id_is_not_silently_replaced(node):
    import asyncio

    from rustchain_sdk.exceptions import APIError

    wallet = SdkWallet.create(strength=128)
    node.fund(wallet.address)
    posted = []

    async def run():
        async with _sdk_client_on_node(node, posted) as client:
            await client.wallet_transfer_with_wallet(wallet, TO, 1.0, chain_id=STALE_CHAIN)

    with pytest.raises(APIError) as exc:
        asyncio.run(run())
    assert exc.value.status_code == 400
    assert "chain_id does not match" in exc.value.response_body["error"]
    assert posted == [STALE_CHAIN]


def _run_nodejs_tip(script_body, env=None):
    """Load discord-bot-nodejs-v2/commands/tip.js with discord.js/tweetnacl stubbed."""
    tip = ROOT / "discord-bot-nodejs-v2" / "commands" / "tip.js"
    script = f"""
const Module = require("module");
const nacl = require({json.dumps(str(NACL_JS))});
const origLoad = Module._load;
Module._load = function (req, parent, isMain) {{
  if (req === "discord.js") {{
    class B {{ constructor() {{ const px = new Proxy(this, {{ get: (t, k) => (k in t ? t[k] : () => px) }}); return px; }} }}
    return {{ SlashCommandBuilder: B, EmbedBuilder: B }};
  }}
  if (req === "tweetnacl") return nacl;
  if (req === "tweetnacl-util") return {{ decodeBase64: (s) => new Uint8Array(Buffer.from(s, "base64")) }};
  return origLoad.apply(this, arguments);
}};
const tip = require({json.dumps(str(tip))});
(async () => {{ {script_body} }})().then(
  (r) => console.log(JSON.stringify(r)),
  (e) => console.log(JSON.stringify({{ thrown: e.message }})));
"""
    import os
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60,
                         check=False, env={**os.environ, **(env or {})})
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@needs_node
def test_nodejs_tip_rejects_malformed_chain_id_override():
    out = _run_nodejs_tip("return await tip._internal.getChainId();",
                          env={"RUSTCHAIN_CHAIN_ID": "bad id"})
    assert "RUSTCHAIN_CHAIN_ID" in out["thrown"]


@needs_node
def test_nodejs_tip_refetches_stale_chain_id_once(node):
    _, _, addr = _key(36)
    node.fund(addr)
    # Scripted node: /network/info reports first STALE (cached), then the real chain;
    # the transfer endpoint answers with what the real node answers for each body.
    js = f"""
const nacl = require({json.dumps(str(NACL_JS))});
const kp = nacl.sign.keyPair.fromSeed(new Uint8Array(32).fill(36));
const infos = [{json.dumps(STALE_CHAIN)}, {json.dumps(node.chain_id)}];
const posted = [];
global.fetch = async (url, opts) => {{
  if (url.endsWith("/network/info")) return {{ ok: true, status: 200, json: async () => ({{ chain_id: infos.shift() }}) }};
  const body = JSON.parse(opts.body);
  posted.push(body);
  const mismatch = body.chain_id !== {json.dumps(node.chain_id)};
  return {{ ok: !mismatch, status: mismatch ? 400 : 200,
           json: async () => (mismatch ? {{ error: "chain_id does not match active network" }} : {{ ok: true }}) }};
}};
const res = await tip._internal.sendChainBoundTransfer({{
  secretKeyBytes: kp.secretKey, toAddress: {json.dumps(TO)}, amountRtc: 1.0, memo: "stale" }});
return {{ res, posted }};
"""
    out = _run_nodejs_tip(js)
    assert out["res"] == {"ok": True}
    assert [b["chain_id"] for b in out["posted"]] == [STALE_CHAIN, node.chain_id]
    # The re-signed request is one the real node verifier accepts.
    assert out["posted"][1]["from_address"] == addr
    node.assert_chain_bound_and_accepted(out["posted"][1])
