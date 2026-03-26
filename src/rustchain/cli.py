"""
RustChain CLI
Command-line interface for RustChain network.

Usage:
    rustchain balance <wallet_id>
    rustchain health
    rustchain epoch
    rustchain miners
    rustchain transfer <from> <to> <amount> [--fee N] [--seed <seed>]
    rustchain wallet generate
    rustchain wallet sign <from> <to> <amount>
"""

import argparse
import sys
from . import RustChainClient, AsyncRustChainClient
from .crypto import SigningKey


def main() -> None:
    parser = argparse.ArgumentParser(prog="rustchain", description="RustChain CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # rustchain health
    sub.add_parser("health", help="Check node health")

    # rustchain epoch
    sub.add_parser("epoch", help="Get current epoch info")

    # rustchain miners
    sub.add_parser("miners", help="List active miners")

    # rustchain balance <wallet_id>
    bal = sub.add_parser("balance", help="Check wallet balance")
    bal.add_argument("wallet_id", help="Wallet or miner ID")

    # rustchain transfer <from> <to> <amount> [--fee] [--sig]
    xfer = sub.add_parser("transfer", help="Submit a signed transfer")
    xfer.add_argument("from_wallet")
    xfer.add_argument("to_wallet")
    xfer.add_argument("amount", type=int, help="Amount in smallest units (1 RTC = 1_000_000)")
    xfer.add_argument("--fee", type=int, default=0)
    xfer.add_argument("--sig", required=True, help="Hex Ed25519 signature")

    # rustchain wallet generate
    wgen = sub.add_parser("wallet", help="Wallet subcommands")
    wsub = wgen.add_subparsers(dest="wallet_cmd")

    gen = wsub.add_parser("generate", help="Generate a new Ed25519 wallet")
    gen.add_argument("--seed", help="Optional seed phrase or hex seed")

    sign = wsub.add_parser("sign", help="Sign a transfer payload")
    sign.add_argument("from_wallet")
    sign.add_argument("to_wallet")
    sign.add_argument("amount", type=int)
    sign.add_argument("--fee", type=int, default=0)
    sign.add_argument("--seed", help="Seed to derive key from")

    args = parser.parse_args()
    client = RustChainClient()

    try:
        if args.cmd == "health":
            print(client.health())
        elif args.cmd == "epoch":
            print(client.epoch())
        elif args.cmd == "miners":
            for m in client.miners():
                print(m)
        elif args.cmd == "balance":
            print(client.balance(args.wallet_id))
        elif args.cmd == "transfer":
            print(client.transfer(
                args.from_wallet, args.to_wallet, args.amount,
                signature=args.sig, fee=args.fee,
            ))
        elif args.wallet_cmd == "generate":
            if args.seed:
                key = SigningKey.from_seed(args.seed.encode())
            else:
                key = SigningKey.generate()
            sig = key.sign(b"rustchain-wallet-generated").hex()
            print(f"Private key (hex): {sig[:64]}...")
            print("(Store this securely — it cannot be recovered)")
        elif args.wallet_cmd == "sign":
            if args.seed:
                key = SigningKey.from_seed(args.seed.encode())
            else:
                key = SigningKey.generate()
            sig_hex, payload = key.sign_transfer(
                args.from_wallet, args.to_wallet, args.amount, args.fee,
            )
            print(f"Signature: {sig_hex}")
            print(f"Payload: {payload}")
        else:
            parser.print_help()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
