"""CLI wrapper for the RustChain SDK.

Usage examples:
    rustchain balance my-wallet
    rustchain transfer <from> <to> <amount> <signature>
    rustchain miners
    rustchain epoch
    rustchain health
    rustchain blocks
    rustchain transactions
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

import httpx

from rustchain.client import RustChainClient
from rustchain.exceptions import RustChainError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("rustchain-cli")


def _json_print(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


async def cmd_health(args: list[str]) -> int:
    """Check node health."""
    async with RustChainClient() as client:
        result = await client.health()
    _json_print(result.model_dump())
    return 0


async def cmd_epoch(args: list[str]) -> int:
    """Show current epoch info."""
    async with RustChainClient() as client:
        result = await client.epoch()
    _json_print(result.model_dump())
    return 0


async def cmd_miners(args: list[str]) -> int:
    """List active miners."""
    page = 1
    per_page = 20
    if len(args) >= 1:
        try:
            page = int(args[0])
        except ValueError:
            logger.error("Page must be an integer")
            return 1
    if len(args) >= 2:
        try:
            per_page = int(args[1])
        except ValueError:
            logger.error("per_page must be an integer")
            return 1

    async with RustChainClient() as client:
        result = await client.miners(page=page, per_page=per_page)
    _json_print(result.model_dump())
    return 0


async def cmd_balance(args: list[str]) -> int:
    """Check wallet balance.

    Usage: rustchain balance <wallet_id>
    """
    if len(args) < 1:
        logger.error("Usage: rustchain balance <wallet_id>")
        return 1

    wallet_id = args[0]
    async with RustChainClient() as client:
        result = await client.balance(wallet_id)
    _json_print(result.model_dump())
    return 0


async def cmd_transfer(args: list[str]) -> int:
    """Submit a signed transfer.

    Usage: rustchain transfer <from_wallet> <to_wallet> <amount> <signature_b64>
    """
    if len(args) < 4:
        logger.error(
            "Usage: rustchain transfer <from_wallet> <to_wallet> <amount> <signature_b64>"
        )
        return 1

    from_wallet, to_wallet, amount_str, signature = args[0], args[1], args[2], args[3]
    try:
        amount = float(amount_str)
    except ValueError:
        logger.error("Amount must be a number")
        return 1

    async with RustChainClient() as client:
        result = await client.transfer(from_wallet, to_wallet, amount, signature)
    _json_print(result.model_dump())
    return 0


async def cmd_attestation(args: list[str]) -> int:
    """Check attestation status of a miner.

    Usage: rustchain attestation <miner_id>
    """
    if len(args) < 1:
        logger.error("Usage: rustchain attestation <miner_id>")
        return 1

    miner_id = args[0]
    async with RustChainClient() as client:
        result = await client.attestation_status(miner_id)
    _json_print(result.model_dump())
    return 0


async def cmd_blocks(args: list[str]) -> int:
    """Show recent blocks."""
    page = 1
    per_page = 20
    if len(args) >= 1:
        try:
            page = int(args[0])
        except ValueError:
            logger.error("Page must be an integer")
            return 1

    async with RustChainClient() as client:
        result = await client.explorer.blocks(page=page, per_page=per_page)
    _json_print(result.model_dump())
    return 0


async def cmd_transactions(args: list[str]) -> int:
    """Show recent transactions."""
    page = 1
    per_page = 20
    if len(args) >= 1:
        try:
            page = int(args[0])
        except ValueError:
            logger.error("Page must be an integer")
            return 1

    async with RustChainClient() as client:
        result = await client.explorer.transactions(page=page, per_page=per_page)
    _json_print(result.model_dump())
    return 0


# Command registry
_COMMANDS: dict[str, tuple[Any, str]] = {
    "health": (cmd_health, ""),
    "epoch": (cmd_epoch, ""),
    "miners": (cmd_miners, "[page] [per_page]"),
    "balance": (cmd_balance, "<wallet_id>"),
    "transfer": (cmd_transfer, "<from_wallet> <to_wallet> <amount> <signature_b64>"),
    "attestation": (cmd_attestation, "<miner_id>"),
    "blocks": (cmd_blocks, "[page]"),
    "transactions": (cmd_transactions, "[page]"),
}


def main() -> int:
    """CLI entry point."""
    if len(sys.argv) < 2 or sys.argv[1] not in _COMMANDS:
        usage = "\n".join(
            f"  rustchain {name} {args}" for name, (_, args) in _COMMANDS.items()
        )
        logger.error(
            "Usage:\n%s\n\nSupported commands:\n%s",
            "  rustchain <command> [args...]",
            usage,
        )
        return 1

    cmd_name = sys.argv[1]
    handler, arg_spec = _COMMANDS[cmd_name]
    args = sys.argv[2:]

    try:
        return asyncio.run(handler(args))
    except RustChainError as e:
        logger.error("RustChain error: %s", e.message)
        if e.details:
            logger.error("Details: %s", e.details)
        return 1
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
