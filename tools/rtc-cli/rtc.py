#!/usr/bin/env python3
"""
rtc — Unified RustChain CLI

A comprehensive command-line interface for all RustChain node operations.
Combines status checks, wallet management, block inspection, miner queries,
configuration validation, and backup management in a single tool.

Usage:
    rtc status                          # node health + epoch + miners
    rtc wallet create [--name NAME]     # create new wallet
    rtc wallet balance <wallet_id>      # check balance
    rtc wallet send <to> <amount> --from <wallet>
    rtc wallet history <wallet_id>      # transaction history
    rtc blocks list [--limit N]         # recent blocks/headers
    rtc blocks get <slot>               # get block by slot
    rtc miners list                     # active miners
    rtc miners info <miner_id>          # miner details + balance
    rtc config validate                 # validate config file
    rtc backup create [--output PATH]   # create node backup
    rtc backup restore <file>           # restore from backup
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import shutil
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CONFIG_DIR = Path.home() / ".rtc"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
KEYSTORE_DIR = CONFIG_DIR / "wallets"
BACKUP_DIR = CONFIG_DIR / "backups"

DEFAULT_NODE_URLS = [
    "https://rustchain.org",
    "https://50.28.86.131",
    "https://50.28.86.153",
]

# ---------------------------------------------------------------------------
# Color helpers (rich-style, no dependency)
# ---------------------------------------------------------------------------

_NO_COLOR = os.environ.get("NO_COLOR") is not None


def _supports_color() -> bool:
    if _NO_COLOR:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return os.environ.get("TERM") is not None
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


def magenta(t: str) -> str:
    return _c("35", t)


# ---------------------------------------------------------------------------
# Config file support
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Load config from ~/.rtc/config.yaml (basic YAML subset parser)."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        text = CONFIG_FILE.read_text(encoding="utf-8")
        # Minimal YAML parser for flat key: value pairs
        cfg: dict = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val.lower() in ("true", "yes"):
                    cfg[key] = True
                elif val.lower() in ("false", "no"):
                    cfg[key] = False
                elif val.isdigit():
                    cfg[key] = int(val)
                else:
                    cfg[key] = val
        return cfg
    except Exception:
        return {}


def _get_node_url() -> str:
    """Resolve node URL: env var > config file > auto-discover."""
    env = os.environ.get("RUSTCHAIN_NODE_URL") or os.environ.get("RUSTCHAIN_NODE")
    if env:
        return env.rstrip("/")

    cfg = _load_config()
    if cfg.get("node_url"):
        return str(cfg["node_url"]).rstrip("/")

    # Auto-discover: try each default until one responds
    for url in DEFAULT_NODE_URLS:
        try:
            _http_get(f"{url}/health", timeout=4)
            return url
        except Exception:
            continue

    return DEFAULT_NODE_URLS[0]


def _verify_ssl() -> bool:
    cfg = _load_config()
    env = os.environ.get("RUSTCHAIN_VERIFY_SSL", "")
    if env:
        return env in ("1", "true", "True")
    return bool(cfg.get("verify_ssl", False))


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# ---------------------------------------------------------------------------

def _ssl_ctx() -> Optional[ssl.SSLContext]:
    if _verify_ssl():
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _http_get(url: str, timeout: int = 10) -> Any:
    req = Request(url, headers={"User-Agent": f"rtc-cli/{__version__}"})
    with urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_post(url: str, data: dict, timeout: int = 15) -> Any:
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, headers={
        "User-Agent": f"rtc-cli/{__version__}",
        "Content-Type": "application/json",
    })
    with urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _api(endpoint: str, method: str = "GET", data: dict | None = None,
         timeout: int = 10) -> Tuple[Any, bool]:
    """Call RustChain API. Returns (data, success)."""
    url = f"{_get_node_url()}{endpoint}"
    try:
        if method == "POST" and data is not None:
            result = _http_post(url, data, timeout)
        else:
            result = _http_get(url, timeout)
        return result, True
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {"error": f"HTTP {e.code}", "url": url}
        return body, False
    except URLError as e:
        return {"error": str(e.reason), "url": url}, False
    except Exception as e:
        return {"error": str(e), "url": url}, False


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _header(title: str) -> None:
    w = max(50, len(title) + 4)
    print(bold(cyan(f"{'=' * w}")))
    print(bold(cyan(f"  {title}")))
    print(bold(cyan(f"{'=' * w}")))


def _kv(key: str, value: Any, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{dim(key + ':')} {value}")


def _status_dot(ok: bool) -> str:
    return green("●") if ok else red("●")


def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}h {m}m"


def _format_rtc(amount: float) -> str:
    return f"{amount:,.6f} RTC"


def _ts_str(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Wallet crypto helpers
# ---------------------------------------------------------------------------

def _derive_ed25519(mnemonic_phrase: str, passphrase: str = ""):
    """Derive (private_hex, public_hex) from BIP39 mnemonic."""
    try:
        from mnemonic import Mnemonic
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError:
        print(red("Error: Missing dependencies. Install: pip install mnemonic cryptography"))
        sys.exit(1)

    m = Mnemonic("english")
    if not m.check(mnemonic_phrase):
        print(red("Error: Invalid BIP39 mnemonic"))
        sys.exit(1)

    seed = Mnemonic.to_seed(mnemonic_phrase, passphrase=passphrase)
    i = hmac.new(b"ed25519 seed", seed, hashlib.sha512).digest()
    sk = i[:32]
    priv = Ed25519PrivateKey.from_private_bytes(sk)
    pub = priv.public_key().public_bytes_raw().hex()
    return sk.hex(), pub


def _address_from_pubkey(pub_hex: str) -> str:
    return "RTC" + hashlib.sha256(bytes.fromhex(pub_hex)).hexdigest()[:40]


def _encrypt_key(priv_hex: str, password: str) -> dict:
    import secrets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000, dklen=32)
    ct = AESGCM(key).encrypt(nonce, bytes.fromhex(priv_hex), None)
    return {
        "cipher": "AES-256-GCM",
        "kdf": "PBKDF2-HMAC-SHA256",
        "kdf_iterations": 100000,
        "salt_b64": base64.b64encode(salt).decode(),
        "nonce_b64": base64.b64encode(nonce).decode(),
        "ciphertext_b64": base64.b64encode(ct).decode(),
    }


def _decrypt_key(enc: dict, password: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = base64.b64decode(enc.get("salt_b64") or enc.get("salt", ""))
    nonce = base64.b64decode(enc.get("nonce_b64") or enc.get("nonce") or enc.get("iv_b64", ""))
    ct = base64.b64decode(enc.get("ciphertext_b64") or enc.get("ciphertext") or enc.get("encrypted_private_key", ""))
    iters = int(enc.get("kdf_iterations", 100000))
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iters, dklen=32)
    pt = AESGCM(key).decrypt(nonce, ct, None)
    return pt.hex()


def _read_password(prompt: str, env_key: str = "RUSTCHAIN_WALLET_PASSWORD") -> str:
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    return getpass.getpass(prompt)


def _keystore_path(name: str) -> Path:
    safe = "".join(c for c in name if c.isalnum() or c in "-_.")
    if not safe:
        raise ValueError("Invalid wallet name")
    return KEYSTORE_DIR / f"{safe}.json"


def _sign_transfer(priv_hex: str, from_addr: str, to_addr: str,
                   amount_rtc: float, memo: str, nonce: int) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    tx = {"from": from_addr, "to": to_addr, "amount": amount_rtc,
          "memo": memo, "nonce": str(nonce)}
    message = json.dumps(tx, sort_keys=True, separators=(",", ":")).encode()
    priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
    sig = priv.sign(message).hex()
    pub = priv.public_key().public_bytes_raw().hex()
    return {
        "from_address": from_addr, "to_address": to_addr,
        "amount_rtc": amount_rtc, "nonce": nonce, "memo": memo,
        "public_key": pub, "signature": sig,
    }


# ===========================================================================
# Subcommands
# ===========================================================================

# ---- status ---------------------------------------------------------------

def cmd_status(args):
    """Show node health, epoch info, and active miners summary."""
    _header("RustChain Node Status")
    node = _get_node_url()
    _kv("Node", node)
    print()

    # Health
    health, ok = _api("/health")
    if ok and isinstance(health, dict):
        h_ok = health.get("ok", False)
        print(f"  {_status_dot(h_ok)} Health: {green('HEALTHY') if h_ok else red('UNHEALTHY')}")
        _kv("Version", health.get("version", "unknown"), 4)
        _kv("Uptime", _format_age(health.get("uptime_s", 0)), 4)
        _kv("DB R/W", green("OK") if health.get("db_rw") else red("FAIL"), 4)
        ba = health.get("backup_age_hours")
        if ba is not None:
            color = green if ba < 24 else (yellow if ba < 36 else red)
            _kv("Backup Age", color(f"{ba:.1f}h"), 4)
        ta = health.get("tip_age_slots")
        if ta is not None:
            _kv("Tip Age", f"{ta} slots", 4)
    else:
        print(f"  {red('●')} Health: {red('UNREACHABLE')}")
        if isinstance(health, dict) and health.get("error"):
            _kv("Error", red(health["error"]), 4)
    print()

    # Epoch
    epoch_data, ok = _api("/epoch")
    if ok and isinstance(epoch_data, dict):
        print(f"  {bold('Epoch Information')}")
        _kv("Epoch", bold(str(epoch_data.get("epoch", "?"))), 4)
        _kv("Slot", epoch_data.get("slot", "?"), 4)
        _kv("Height", epoch_data.get("height", "?"), 4)
    print()

    # Stats
    stats, ok = _api("/api/stats")
    if ok and isinstance(stats, dict):
        print(f"  {bold('Network Statistics')}")
        _kv("Chain ID", stats.get("chain_id", "?"), 4)
        _kv("Total Miners", stats.get("total_miners", "?"), 4)
        tb = stats.get("total_balance")
        if tb is not None:
            _kv("Total Supply", _format_rtc(tb), 4)
        feats = stats.get("features", [])
        if feats:
            _kv("Features", ", ".join(feats), 4)
    print()

    # Chain tip
    tip, ok = _api("/headers/tip")
    if ok and isinstance(tip, dict) and tip.get("slot"):
        print(f"  {bold('Chain Tip')}")
        _kv("Slot", tip.get("slot", "?"), 4)
        _kv("Miner", tip.get("miner", "?"), 4)
        ta = tip.get("tip_age")
        if ta is not None:
            _kv("Tip Age", _format_age(ta), 4)
    print()

    # Active miners count
    miners, ok = _api("/api/miners")
    if ok and isinstance(miners, dict):
        mlist = miners.get("miners", [])
        print(f"  {bold('Active Miners')}: {green(str(len(mlist)))}")
    elif ok and isinstance(miners, list):
        print(f"  {bold('Active Miners')}: {green(str(len(miners)))}")

    return 0


# ---- wallet ---------------------------------------------------------------

def cmd_wallet_create(args):
    """Create a new wallet with 24-word mnemonic."""
    try:
        from mnemonic import Mnemonic
    except ImportError:
        print(red("Error: Missing 'mnemonic' package. Install: pip install mnemonic cryptography"))
        return 1

    KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)
    wallet_name = args.name or f"wallet-{int(time.time())}"
    password = _read_password("Set wallet password: ")
    confirm = _read_password("Confirm password: ", "RUSTCHAIN_WALLET_PASSWORD_CONFIRM")
    if password != confirm:
        print(red("Error: Passwords do not match"))
        return 1

    m = Mnemonic("english")
    phrase = m.generate(strength=256)
    priv_hex, pub_hex = _derive_ed25519(phrase)
    address = _address_from_pubkey(pub_hex)

    ks = {
        "version": 1, "name": wallet_name, "address": address,
        "public_key_hex": pub_hex, "mnemonic_words": 24,
        "crypto": _encrypt_key(priv_hex, password),
        "created_at": int(time.time()),
    }
    path = _keystore_path(wallet_name)
    path.write_text(json.dumps(ks, indent=2))

    _header("Wallet Created")
    _kv("Name", green(wallet_name))
    _kv("Address", bold(address))
    _kv("Keystore", str(path))
    print()
    print(yellow("  Seed phrase (write down and keep safe):"))
    print(f"  {bold(phrase)}")
    return 0


def cmd_wallet_balance(args):
    """Check wallet balance."""
    data, ok = _api(f"/wallet/balance?miner_id={args.wallet_id}")
    if not ok:
        print(red(f"Error: {data.get('error', 'Request failed')}"))
        return 1

    _header("Wallet Balance")
    _kv("Wallet", args.wallet_id)
    amt = data.get("amount_rtc", data.get("balance_rtc", 0))
    _kv("Balance", bold(green(_format_rtc(amt))))
    _kv("Raw (i64)", data.get("amount_i64", 0))

    if args.json:
        print()
        print(json.dumps(data, indent=2))
    return 0


def cmd_wallet_send(args):
    """Send a signed transfer."""
    ks_path = _keystore_path(args.from_wallet)
    if not ks_path.exists():
        print(red(f"Error: Wallet '{args.from_wallet}' not found at {ks_path}"))
        return 1

    ks = json.loads(ks_path.read_text())
    password = _read_password("Wallet password: ")

    try:
        priv_hex = _decrypt_key(ks["crypto"], password)
    except Exception as e:
        print(red(f"Error: Failed to decrypt wallet — {e}"))
        return 1

    from_addr = ks["address"]
    nonce = int(time.time())
    payload = _sign_transfer(priv_hex, from_addr, args.to, float(args.amount),
                             args.memo or "", nonce)

    data, ok = _api("/wallet/transfer/signed", method="POST", data=payload, timeout=20)
    if ok:
        _header("Transfer Submitted")
        _kv("From", from_addr)
        _kv("To", args.to)
        _kv("Amount", _format_rtc(float(args.amount)))
        print()
        print(green("  Transaction submitted successfully."))
        if isinstance(data, dict):
            print(json.dumps(data, indent=2))
    else:
        print(red("Transfer failed:"))
        print(json.dumps(data, indent=2))
        return 1
    return 0


def cmd_wallet_history(args):
    """Show wallet transaction history."""
    params = f"miner_id={args.wallet_id}"
    if args.limit:
        params += f"&limit={args.limit}"
    data, ok = _api(f"/wallet/history?{params}")
    if not ok:
        # Fall back to /wallet/ledger
        data, ok = _api(f"/wallet/ledger?miner_id={args.wallet_id}")
    if not ok:
        print(red(f"Error: {data.get('error', 'Request failed')}"))
        return 1

    _header(f"Transaction History — {args.wallet_id}")

    txs = data if isinstance(data, list) else data.get("transactions", data.get("history", []))
    if not txs:
        print(dim("  No transactions found."))
        return 0

    for i, tx in enumerate(txs[:50]):
        idx = dim(f"[{i+1:3d}]")
        from_addr = tx.get("from", tx.get("from_address", "?"))
        to_addr = tx.get("to", tx.get("to_address", "?"))
        amt = tx.get("amount_rtc", tx.get("amount", 0))
        ts = tx.get("timestamp", tx.get("ts", 0))
        ts_s = _ts_str(ts) if ts else "?"
        direction = green("IN ") if to_addr == args.wallet_id else red("OUT")
        print(f"  {idx} {direction} {_format_rtc(float(amt)):>20s}  {from_addr} -> {to_addr}  {dim(ts_s)}")

    print(f"\n  {dim(f'Showing {min(len(txs), 50)} of {len(txs)} transactions')}")
    return 0


# ---- blocks ---------------------------------------------------------------

def cmd_blocks_list(args):
    """List recent blocks/headers."""
    # Use headers/tip for chain state, /api/stats for context
    tip, ok = _api("/headers/tip")
    if not ok:
        print(red(f"Error: Could not reach node — {tip.get('error', '?')}"))
        return 1

    _header("Recent Blocks")

    if isinstance(tip, dict) and tip.get("slot"):
        print(f"  {bold('Chain Tip')}")
        _kv("Slot", bold(str(tip["slot"])), 4)
        _kv("Miner", tip.get("miner", "?"), 4)
        ta = tip.get("tip_age")
        if ta is not None:
            _kv("Age", _format_age(ta), 4)
        sig = tip.get("signature_prefix", "")
        if sig:
            _kv("Sig Prefix", dim(sig), 4)
    else:
        print(dim("  No chain tip data available."))

    print()

    # Get epoch info for context
    epoch, ok = _api("/epoch")
    if ok and isinstance(epoch, dict):
        _kv("Current Epoch", epoch.get("epoch", "?"))
        _kv("Current Slot", epoch.get("slot", "?"))
        _kv("Block Height", epoch.get("height", "?"))

    if args.json:
        out = {"tip": tip}
        if ok:
            out["epoch"] = epoch
        print()
        print(json.dumps(out, indent=2))

    return 0


def cmd_blocks_get(args):
    """Get block details by slot number."""
    # Try rewards for that epoch (slot -> epoch mapping)
    _header(f"Block / Slot #{args.slot}")

    tip, ok = _api("/headers/tip")
    if ok and isinstance(tip, dict):
        current = tip.get("slot", 0)
        if args.slot > current:
            print(yellow(f"  Slot {args.slot} has not been produced yet (current: {current})"))
            return 1

    # Show epoch rewards if applicable
    epoch_num = args.slot  # User can query by epoch number too
    data, ok = _api(f"/rewards/epoch/{epoch_num}")
    if ok and isinstance(data, dict):
        rewards = data.get("rewards", [])
        if rewards:
            print(f"  {bold('Epoch Rewards')} (epoch {data.get('epoch', epoch_num)})")
            for r in rewards[:20]:
                mid = r.get("miner_id", "?")
                share = r.get("share_rtc", r.get("share_i64", 0))
                print(f"    {mid:30s}  {_format_rtc(float(share))}")
            if len(rewards) > 20:
                print(dim(f"    ... and {len(rewards) - 20} more"))
        else:
            print(dim("  No reward data for this epoch/slot."))
    else:
        print(dim("  No block data available for this slot."))

    if args.json:
        print()
        print(json.dumps(data if isinstance(data, dict) else {}, indent=2))

    return 0


# ---- miners ---------------------------------------------------------------

def cmd_miners_list(args):
    """List active miners."""
    data, ok = _api("/api/miners")
    if not ok:
        print(red(f"Error: {data.get('error', 'Request failed')}"))
        return 1

    miners = data.get("miners", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    _header(f"Active Miners ({len(miners)})")

    if not miners:
        print(dim("  No active miners found."))
        return 0

    # Table header
    print(f"  {'Miner':<30s} {'Hardware':<25s} {'Multiplier':>10s} {'Last Seen':>12s}")
    print(f"  {'-'*30} {'-'*25} {'-'*10} {'-'*12}")

    for m in miners:
        name = m.get("miner", m.get("miner_id", "?"))[:30]
        hw = m.get("hardware_type", m.get("device_family", "unknown"))[:25]
        mult = m.get("antiquity_multiplier", m.get("multiplier", 1.0))
        last = m.get("last_attestation_age", m.get("ts_ok"))
        if isinstance(last, int) and last > 1_000_000_000:
            age = int(time.time()) - last
            last_s = _format_age(age)
        elif isinstance(last, int):
            last_s = _format_age(last)
        else:
            last_s = "?"

        mult_s = f"{mult:.2f}x"
        if mult > 1.5:
            mult_s = magenta(mult_s)
        elif mult > 1.0:
            mult_s = cyan(mult_s)

        print(f"  {name:<30s} {hw:<25s} {mult_s:>10s} {last_s:>12s}")

    if args.json:
        print()
        print(json.dumps(data, indent=2))

    return 0


def cmd_miners_info(args):
    """Show detailed info for a specific miner."""
    _header(f"Miner: {args.miner_id}")

    # Get balance
    bal, ok = _api(f"/wallet/balance?miner_id={args.miner_id}")
    if ok and isinstance(bal, dict):
        amt = bal.get("amount_rtc", bal.get("balance_rtc", 0))
        print(f"  {bold('Balance')}: {green(_format_rtc(amt))}")
    else:
        print(f"  {bold('Balance')}: {dim('unknown')}")
    print()

    # Get from miners list
    data, ok = _api("/api/miners")
    if ok:
        miners = data.get("miners", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        found = None
        for m in miners:
            if m.get("miner", m.get("miner_id", "")) == args.miner_id:
                found = m
                break

        if found:
            print(f"  {bold('Attestation Details')}")
            _kv("Hardware", found.get("hardware_type", found.get("device_family", "?")), 4)
            _kv("Architecture", found.get("device_arch", "?"), 4)
            _kv("Multiplier", f"{found.get('antiquity_multiplier', found.get('multiplier', 1.0)):.2f}x", 4)
            _kv("Entropy Score", found.get("entropy_score", "?"), 4)
            first = found.get("first_attestation")
            if first:
                _kv("First Seen", _ts_str(first), 4)
            last = found.get("last_attestation", found.get("ts_ok"))
            if isinstance(last, int) and last > 1_000_000_000:
                _kv("Last Seen", _ts_str(last), 4)
            print(f"\n  {green('●')} Miner is {green('ACTIVE')}")
        else:
            print(f"  {yellow('●')} Miner is {yellow('NOT ACTIVE')} (no recent attestation)")

    if args.json:
        out = {"balance": bal}
        if found:
            out["miner"] = found
        print()
        print(json.dumps(out, indent=2))

    return 0


# ---- config ---------------------------------------------------------------

def cmd_config_validate(args):
    """Validate the configuration file."""
    _header("Configuration Validation")

    if not CONFIG_FILE.exists():
        print(yellow(f"  Config file not found: {CONFIG_FILE}"))
        print(dim(f"  Using defaults. Create config at {CONFIG_FILE} to customize."))
        print()
        _show_default_config()
        return 0

    cfg = _load_config()
    errors = []
    warnings = []

    # Validate node_url
    node_url = cfg.get("node_url", "")
    if node_url:
        if not (node_url.startswith("http://") or node_url.startswith("https://")):
            errors.append(f"node_url must start with http:// or https://  (got: {node_url})")
        else:
            # Test connectivity
            try:
                _http_get(f"{node_url.rstrip('/')}/health", timeout=5)
                print(f"  {green('●')} node_url: {node_url} — {green('reachable')}")
            except Exception as e:
                warnings.append(f"node_url {node_url} is unreachable: {e}")
                print(f"  {yellow('●')} node_url: {node_url} — {yellow('unreachable')}")
    else:
        print(f"  {dim('●')} node_url: {dim('not set (using auto-discover)')}")

    # Validate verify_ssl
    vs = cfg.get("verify_ssl")
    if vs is not None:
        print(f"  {'●'} verify_ssl: {vs}")

    # Validate wallet_dir
    wd = cfg.get("wallet_dir")
    if wd:
        wp = Path(wd)
        if wp.exists():
            print(f"  {green('●')} wallet_dir: {wd} — {green('exists')}")
        else:
            warnings.append(f"wallet_dir {wd} does not exist")
            print(f"  {yellow('●')} wallet_dir: {wd} — {yellow('missing')}")

    print()
    if errors:
        for e in errors:
            print(f"  {red('ERROR')}: {e}")
        return 1
    if warnings:
        for w in warnings:
            print(f"  {yellow('WARN')}: {w}")
    print(f"  {green('Config is valid.')}")
    return 0


def _show_default_config():
    print(dim("  Example ~/.rtc/config.yaml:"))
    print()
    example = [
        "# RustChain CLI configuration",
        "node_url: https://rustchain.org",
        "verify_ssl: false",
        "# wallet_dir: ~/.rtc/wallets",
        "# backup_dir: ~/.rtc/backups",
    ]
    for line in example:
        print(f"  {dim(line)}")


# ---- backup ---------------------------------------------------------------

def cmd_backup_create(args):
    """Create a backup of local wallet keystores and config."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = args.output or str(BACKUP_DIR / f"rtc-backup-{ts}")

    _header("Creating Backup")

    files_backed = []

    # Backup config
    if CONFIG_FILE.exists():
        files_backed.append(("config.yaml", CONFIG_FILE))

    # Backup wallets
    if KEYSTORE_DIR.exists():
        for f in KEYSTORE_DIR.glob("*.json"):
            files_backed.append((f"wallets/{f.name}", f))

    if not files_backed:
        print(yellow("  Nothing to back up (no config or wallets found)."))
        return 0

    # Create tar.gz if available, else zip
    try:
        import tarfile
        archive_path = f"{out_name}.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            for arcname, filepath in files_backed:
                tar.add(str(filepath), arcname=f"rtc-backup/{arcname}")
        print(f"  {green('●')} Backup created: {bold(archive_path)}")
    except Exception:
        import zipfile
        archive_path = f"{out_name}.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arcname, filepath in files_backed:
                zf.write(str(filepath), f"rtc-backup/{arcname}")
        print(f"  {green('●')} Backup created: {bold(archive_path)}")

    print(f"  Files included: {len(files_backed)}")
    for arcname, _ in files_backed:
        print(f"    {dim(arcname)}")

    return 0


def cmd_backup_restore(args):
    """Restore wallets and config from a backup archive."""
    archive = Path(args.file)
    if not archive.exists():
        print(red(f"Error: File not found: {archive}"))
        return 1

    _header("Restoring Backup")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)

    restored = 0
    try:
        if str(archive).endswith(".tar.gz") or str(archive).endswith(".tgz"):
            import tarfile
            with tarfile.open(str(archive), "r:gz") as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        name = member.name
                        # Strip leading rtc-backup/ prefix
                        if "/" in name:
                            rel = name.split("/", 1)[1] if name.startswith("rtc-backup/") else name
                        else:
                            rel = name

                        if rel == "config.yaml":
                            dest = CONFIG_FILE
                        elif rel.startswith("wallets/"):
                            dest = KEYSTORE_DIR / rel.split("/", 1)[1]
                        else:
                            continue

                        f = tar.extractfile(member)
                        if f:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            dest.write_bytes(f.read())
                            print(f"  {green('●')} Restored: {rel}")
                            restored += 1
        elif str(archive).endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(str(archive), "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename
                    rel = name.split("/", 1)[1] if name.startswith("rtc-backup/") else name

                    if rel == "config.yaml":
                        dest = CONFIG_FILE
                    elif rel.startswith("wallets/"):
                        dest = KEYSTORE_DIR / rel.split("/", 1)[1]
                    else:
                        continue

                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(zf.read(info))
                    print(f"  {green('●')} Restored: {rel}")
                    restored += 1
        else:
            print(red("Error: Unsupported archive format. Use .tar.gz or .zip"))
            return 1
    except Exception as e:
        print(red(f"Error during restore: {e}"))
        return 1

    print(f"\n  {green(f'Restored {restored} file(s).')}")
    return 0


# ===========================================================================
# Argument parser
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rtc",
        description="Unified RustChain CLI — node status, wallets, blocks, miners, config & backups",
    )
    p.add_argument("-v", "--version", action="version", version=f"rtc {__version__}")
    p.add_argument("--json", action="store_true", help="Output raw JSON where applicable")
    p.add_argument("--node", help="Override node URL", metavar="URL")
    sub = p.add_subparsers(dest="command", help="Available commands")

    # --- status ---
    p_status = sub.add_parser("status", help="Node health, epoch, and network summary")
    p_status.set_defaults(func=cmd_status)

    # --- wallet ---
    p_wallet = sub.add_parser("wallet", help="Wallet management")
    wsub = p_wallet.add_subparsers(dest="wallet_cmd")

    pw_create = wsub.add_parser("create", help="Create a new wallet")
    pw_create.add_argument("--name", help="Wallet name (default: wallet-<timestamp>)")
    pw_create.set_defaults(func=cmd_wallet_create)

    pw_bal = wsub.add_parser("balance", help="Check wallet balance")
    pw_bal.add_argument("wallet_id", help="Wallet address or miner ID")
    pw_bal.set_defaults(func=cmd_wallet_balance)

    pw_send = wsub.add_parser("send", help="Send a signed RTC transfer")
    pw_send.add_argument("to", help="Recipient address")
    pw_send.add_argument("amount", type=float, help="Amount in RTC")
    pw_send.add_argument("--from", dest="from_wallet", required=True, help="Local wallet name")
    pw_send.add_argument("--memo", default="", help="Optional memo")
    pw_send.set_defaults(func=cmd_wallet_send)

    pw_hist = wsub.add_parser("history", help="Transaction history")
    pw_hist.add_argument("wallet_id", help="Wallet address or miner ID")
    pw_hist.add_argument("--limit", type=int, default=50, help="Max transactions (default: 50)")
    pw_hist.set_defaults(func=cmd_wallet_history)

    # --- blocks ---
    p_blocks = sub.add_parser("blocks", help="Block inspection")
    bsub = p_blocks.add_subparsers(dest="blocks_cmd")

    pb_list = bsub.add_parser("list", help="List recent blocks")
    pb_list.set_defaults(func=cmd_blocks_list)

    pb_get = bsub.add_parser("get", help="Get block details by slot")
    pb_get.add_argument("slot", type=int, help="Slot number")
    pb_get.set_defaults(func=cmd_blocks_get)

    # --- miners ---
    p_miners = sub.add_parser("miners", help="Miner information")
    msub = p_miners.add_subparsers(dest="miners_cmd")

    pm_list = msub.add_parser("list", help="List active miners")
    pm_list.set_defaults(func=cmd_miners_list)

    pm_info = msub.add_parser("info", help="Detailed miner info")
    pm_info.add_argument("miner_id", help="Miner ID")
    pm_info.set_defaults(func=cmd_miners_info)

    # --- config ---
    p_config = sub.add_parser("config", help="Configuration management")
    csub = p_config.add_subparsers(dest="config_cmd")

    pc_val = csub.add_parser("validate", help="Validate configuration file")
    pc_val.set_defaults(func=cmd_config_validate)

    # --- backup ---
    p_backup = sub.add_parser("backup", help="Backup and restore")
    bksub = p_backup.add_subparsers(dest="backup_cmd")

    pbk_create = bksub.add_parser("create", help="Create backup of wallets and config")
    pbk_create.add_argument("--output", help="Output path (without extension)")
    pbk_create.set_defaults(func=cmd_backup_create)

    pbk_restore = bksub.add_parser("restore", help="Restore from backup archive")
    pbk_restore.add_argument("file", help="Backup archive path (.tar.gz or .zip)")
    pbk_restore.set_defaults(func=cmd_backup_restore)

    return p


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Apply --node override
    if hasattr(args, "node") and args.node:
        os.environ["RUSTCHAIN_NODE_URL"] = args.node

    # Propagate --json to all subcommands
    if not hasattr(args, "json"):
        args.json = False

    if hasattr(args, "func"):
        try:
            return args.func(args) or 0
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 130
        except Exception as e:
            print(red(f"Error: {e}"))
            return 1
    else:
        parser.parse_args([args.command, "-h"])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
