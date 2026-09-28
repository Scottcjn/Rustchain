# SPDX-License-Identifier: MIT
"""Chain-bound request builder for ``POST /wallet/transfer/signed``.

Kept free of GUI / network imports so the exact bytes the wallet signs can be
checked against the node's verifier in tests
(tests/test_signed_transfer_clients_chain_id.py).

The node rebuilds the signed message as (node/rustchain_v2_integrated_v2.2.1_rip200.py,
``_wallet_transfer_signed_messages``)::

    json.dumps({"amount": float, "chain_id": str, "from": str, "memo": str,
                "nonce": str(nonce), "to": str},
               sort_keys=True, separators=(",", ":"))

That is the fee-less ("legacy") form, accepted when ``fee_rtc`` is 0. ``chain_id``
binds the signature to one network so it cannot be replayed on another
(testnet <-> mainnet, forks); it must equal the node's ``CHAIN_ID``, which the
node publishes at ``GET /network/info``.
"""

from __future__ import annotations

import json
import math
import re
import time
from typing import Any, Dict, Optional

_CHAIN_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def validate_chain_id(chain_id: Any) -> str:
    """Return ``chain_id`` if it is a well-formed chain id, else raise ValueError."""
    if not isinstance(chain_id, str) or not _CHAIN_ID_RE.fullmatch(chain_id):
        raise ValueError(f"invalid chain_id: {chain_id!r}")
    return chain_id


def chain_id_from_network_info(info: Any) -> str:
    """Extract and validate ``chain_id`` from a ``GET /network/info`` response."""
    if not isinstance(info, dict):
        raise ValueError("network info response is not a JSON object")
    return validate_chain_id(info.get("chain_id"))


def canonical_transfer_message(
    from_address: str,
    to_address: str,
    amount_rtc: float,
    memo: str,
    nonce: int,
    chain_id: str,
) -> bytes:
    """The exact bytes the node verifies for a fee-less, chain-bound transfer."""
    tx_data = {
        "from": from_address,
        "to": to_address,
        "amount": float(amount_rtc),
        "memo": memo,
        "nonce": str(nonce),
        "chain_id": validate_chain_id(chain_id),
    }
    return json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()


def build_signed_transfer(
    wallet: Any,
    to_address: str,
    amount_rtc: float,
    memo: str,
    chain_id: str,
    nonce: Optional[int] = None,
) -> Dict[str, Any]:
    """Sign a transfer with ``wallet`` and return the request body.

    ``wallet`` needs ``address``, ``public_key`` (hex) and
    ``sign_message(bytes) -> hex`` (the ``rustchain_crypto.RustChainWallet`` API).
    """
    if isinstance(amount_rtc, bool) or not isinstance(amount_rtc, (int, float)):
        raise TypeError("amount must be a number")
    amount = float(amount_rtc)
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError("amount must be a positive, finite number")
    if nonce is None:
        nonce = int(time.time() * 1000)
    memo = str(memo or "")
    message = canonical_transfer_message(
        wallet.address, to_address, amount, memo, nonce, chain_id
    )
    return {
        "from_address": wallet.address,
        "to_address": to_address,
        "amount_rtc": amount,
        "memo": memo,
        "nonce": int(nonce),
        "chain_id": chain_id,
        "signature": wallet.sign_message(message),
        "public_key": wallet.public_key,
    }
