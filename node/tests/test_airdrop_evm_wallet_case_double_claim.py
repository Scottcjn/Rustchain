"""Regression: the same Base (EVM) wallet must not claim the airdrop twice
just by varying the address' EIP-55 checksum casing.

EVM addresses are case-insensitive: the mixed-case form is only an EIP-55
display checksum over the same 20 bytes. `_has_claimed` compares
`wallet_address = ?` byte-exactly, so `0x5683...9c6` and `0x5683...9c6`
lowercased are treated as two different wallets, defeating the
"One claim per GitHub/wallet" anti-Sybil rule (RIP-305).

Solana addresses are base58 and ARE case-sensitive, so they must keep
byte-exact comparison.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airdrop_v2 import AirdropV2  # noqa: E402

# Real EIP-55 checksummed address (the project's own wRTC contract on Base).
EVM_CHECKSUMMED = "0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6"
EVM_LOWERCASE = EVM_CHECKSUMMED.lower()
EVM_UPPERCASE = "0x" + EVM_CHECKSUMMED[2:].upper()


@pytest.fixture
def airdrop():
    return AirdropV2(":memory:")


def _claimed_uwrtc(airdrop, chain):
    conn = airdrop._get_conn()
    row = conn.execute(
        "SELECT claimed_uwrtc FROM airdrop_allocation WHERE chain = ?", (chain,)
    ).fetchone()
    return row["claimed_uwrtc"]


def test_same_base_wallet_different_checksum_case_rejected(airdrop):
    """Same EVM wallet, different casing, different GitHub -> must be rejected."""
    ok, msg, _ = airdrop.claim_airdrop(
        github_username="alice",
        wallet_address=EVM_CHECKSUMMED,
        chain="base",
        tier="core",
        skip_antisybil=True,
    )
    assert ok, msg

    ok2, msg2, _ = airdrop.claim_airdrop(
        github_username="mallory",
        wallet_address=EVM_LOWERCASE,
        chain="base",
        tier="core",
        skip_antisybil=True,
    )
    assert not ok2, (
        "same Base wallet claimed twice via checksum-case variation: "
        f"{EVM_CHECKSUMMED} then {EVM_LOWERCASE}"
    )

    # 200 wRTC (core tier), not 400.
    assert _claimed_uwrtc(airdrop, "base") == 200 * 1_000_000


def test_same_base_wallet_uppercase_variant_rejected(airdrop):
    ok, _, _ = airdrop.claim_airdrop(
        "alice", EVM_LOWERCASE, "base", "core", skip_antisybil=True
    )
    assert ok
    ok2, _, _ = airdrop.claim_airdrop(
        "mallory", EVM_UPPERCASE, "base", "core", skip_antisybil=True
    )
    assert not ok2


def test_has_claimed_matches_base_wallet_in_any_case(airdrop):
    ok, _, _ = airdrop.claim_airdrop(
        "alice", EVM_CHECKSUMMED, "base", "core", skip_antisybil=True
    )
    assert ok
    assert airdrop._has_claimed("mallory", EVM_LOWERCASE, "base")
    assert airdrop._has_claimed("mallory", EVM_UPPERCASE, "base")


def test_solana_addresses_remain_case_sensitive(airdrop):
    """Base58 Solana addresses are case-sensitive - must NOT be folded."""
    addr_a = "7EqQdEULxWcraVx3mXKFjc84LhCkMGZCkRuDpvcMwJeK"
    addr_b = "7eqqdeulxwcravx3mxkfjc84lhckmgzckrudpvcmwjek"  # different wallet
    ok, _, _ = airdrop.claim_airdrop(
        "alice", addr_a, "solana", "core", skip_antisybil=True
    )
    assert ok
    ok2, msg2, _ = airdrop.claim_airdrop(
        "mallory", addr_b, "solana", "core", skip_antisybil=True
    )
    assert ok2, f"distinct Solana wallet wrongly rejected: {msg2}"
