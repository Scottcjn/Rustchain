#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Android/Termux launcher for the RustChain Python miner.

This keeps the existing Linux miner/fingerprint implementation as the single
source of truth while adding Termux-safe verification modes and node selection.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path
from urllib.parse import urlparse

PRODUCTION_NODE_HOSTS = {"rustchain.org", "www.rustchain.org"}
DEFAULT_NODE_URL = "https://rustchain.org"


def is_termux_android() -> bool:
    """Return True only for a Termux runtime on Android."""
    prefix = os.environ.get("PREFIX", "")
    return platform.system() == "Android" and (
        bool(os.environ.get("TERMUX_VERSION")) or "/com.termux/files/usr" in prefix
    )


def _core_search_paths() -> list[Path]:
    here = Path(__file__).resolve().parent
    # Installed layout puts the core beside this wrapper.  In a source checkout
    # it remains in ../linux so we can test without copying repository files.
    return [here, here.parent / "linux"]


def load_core():
    for path in _core_search_paths():
        if (path / "rustchain_linux_miner.py").is_file():
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))
            import rustchain_linux_miner as core

            return core
    raise RuntimeError(
        "rustchain_linux_miner.py not found; run the Termux installer or use this "
        "wrapper from a RustChain source checkout"
    )


def validate_node_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise argparse.ArgumentTypeError("node URL must be an http(s) URL")
    return value.rstrip("/")


def validate_test_node_url(value: str) -> str:
    """Refuse production for --test-only so the mode cannot alter mainnet state."""
    value = validate_node_url(value)
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    if host in PRODUCTION_NODE_HOSTS:
        raise ValueError(
            "--test-only refuses the production RustChain node; pass an explicit "
            "local/test node with --node-url"
        )
    return value


def _make_miner(core, args, *, persist_key: bool):
    # LocalMiner reads the module-level default during construction. Set it
    # before constructing so even the startup banner reports the selected node.
    core.NODE_URL = args.node_url
    return core.LocalMiner(
        wallet=args.wallet,
        wart_address=None,
        wart_pool=None,
        bzminer_path=None,
        manage_bzminer=False,
        verbose=args.verbose,
        show_payload=False,
        persist_key=persist_key,
    )


def payload_preview(miner) -> dict:
    """Return the hardware portion of an attestation before any network request."""
    miner._get_hw_info()
    if not miner.fingerprint_data and getattr(miner, "_run_fingerprint_checks", None):
        miner._run_fingerprint_checks()
    hw = miner.hw_info
    return {
        "miner": miner.wallet,
        "miner_id": miner._miner_id(),
        "device": {
            "family": hw.get("family"),
            "arch": hw.get("arch"),
            "model": hw.get("cpu", "Unknown"),
            "cpu": hw.get("cpu", "Unknown"),
            "cores": hw.get("cores"),
            "memory_gb": hw.get("memory_gb"),
            "serial": hw.get("serial"),
            "machine": hw.get("machine", platform.machine()),
        },
        "signals": {
            "macs": hw.get("macs", []),
            "hostname": hw.get("hostname"),
        },
        "fingerprint": miner.fingerprint_data,
        "dynamic_at_attestation": {
            "nonce": "<server-issued challenge>",
            "report": "<collected immediately before signing>",
            "signature": "<ephemeral/persistent Ed25519 signature>",
            "public_key": "<derived from Ed25519 keypair>",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RustChain miner launcher for Android/Termux (aarch64/ARM)"
    )
    parser.add_argument("--wallet", help="RTC wallet/miner name")
    parser.add_argument(
        "--node-url",
        type=validate_node_url,
        default=os.environ.get("RUSTCHAIN_NODE", DEFAULT_NODE_URL),
        help="RustChain node URL (default: %(default)s)",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--dry-run",
        action="store_true",
        help="fingerprint + read-only health check; never attest/enroll/mine",
    )
    modes.add_argument(
        "--show-payload",
        action="store_true",
        help="print the local hardware payload; perform no network requests",
    )
    modes.add_argument(
        "--test-only",
        action="store_true",
        help="attest once to an explicit non-production test node and exit",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not is_termux_android():
        parser.error("this launcher requires Android running inside Termux")

    if not args.wallet:
        if args.dry_run or args.show_payload:
            args.wallet = "termux-verification-only"
        else:
            parser.error("--wallet is required for --test-only and normal mining")

    if args.test_only:
        try:
            args.node_url = validate_test_node_url(args.node_url)
        except ValueError as exc:
            parser.error(str(exc))

    core = load_core()

    # Verification modes never write a key to disk.
    persist_key = not (args.dry_run or args.show_payload or args.test_only)
    miner = _make_miner(core, args, persist_key=persist_key)

    if args.show_payload:
        print("[SHOW-PAYLOAD] Local preview only; no network request was made.")
        print(json.dumps(payload_preview(miner), indent=2, sort_keys=True))
        return 0

    if args.dry_run:
        ok = miner.dry_run()
        return 0 if ok else 2

    if args.test_only:
        print(f"[TEST-ONLY] One attestation to {args.node_url}; enroll/mining disabled.")
        ok = miner.attest()
        if miner.hw_info:
            print(
                "[TEST-ONLY] detected="
                f"{miner.hw_info.get('family')}/{miner.hw_info.get('arch')} "
                f"machine={miner.hw_info.get('machine')} cpu={miner.hw_info.get('cpu')}"
            )
        print(f"[TEST-ONLY] fingerprint_passed={bool(miner.fingerprint_passed)}")
        print(f"[TEST-ONLY] attestation_accepted={bool(ok)}")
        return 0 if ok else 2

    result = miner.mine()
    return 0 if result in (None, True, 0) else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
