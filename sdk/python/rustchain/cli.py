"""CLI wrapper: ``rustchain <command> [args]``."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .client import RustChainClient


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2))


async def _run(args: argparse.Namespace) -> None:
    async with RustChainClient(node_url=args.node) as client:
        if args.command == "health":
            _print_json(await client.health())
        elif args.command == "epoch":
            _print_json(await client.epoch())
        elif args.command == "miners":
            _print_json(await client.miners())
        elif args.command == "balance":
            _print_json(await client.balance(args.wallet_id))
        elif args.command == "attestation":
            _print_json(await client.attestation_status(args.miner_id))
        elif args.command == "blocks":
            _print_json(await client.explorer.blocks())
        elif args.command == "transactions":
            _print_json(await client.explorer.transactions())


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rustchain",
        description="RustChain node CLI",
    )
    parser.add_argument(
        "--node",
        default=None,
        help="Node base URL (default: RUSTCHAIN_NODE_URL env or https://50.28.86.131)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Node health check")
    sub.add_parser("epoch", help="Current epoch info")
    sub.add_parser("miners", help="List active miners")

    p_balance = sub.add_parser("balance", help="Check wallet balance")
    p_balance.add_argument("wallet_id", help="Wallet name / miner ID")

    p_attest = sub.add_parser("attestation", help="Check attestation status")
    p_attest.add_argument("miner_id", help="Miner ID")

    sub.add_parser("blocks", help="Recent blocks")
    sub.add_parser("transactions", help="Recent transactions")

    args = parser.parse_args()
    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
