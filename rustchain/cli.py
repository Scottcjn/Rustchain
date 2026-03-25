"""CLI wrapper: rustchain <command> [args]."""
from __future__ import annotations
import argparse
import json
import sys
from .client import RustChainClient

def main() -> None:
    parser = argparse.ArgumentParser(prog="rustchain", description="RustChain CLI")
    parser.add_argument("--node", default="https://50.28.86.131", help="Node URL")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health")
    sub.add_parser("epoch")
    sub.add_parser("miners")

    bal = sub.add_parser("balance")
    bal.add_argument("wallet_id")

    att = sub.add_parser("attestation")
    att.add_argument("miner_id")

    blk = sub.add_parser("blocks")
    blk.add_argument("--limit", type=int, default=10)

    txs = sub.add_parser("transactions")
    txs.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = RustChainClient(node_url=args.node)
    try:
        if args.command == "health":
            r = client.health()
            print(json.dumps(r.raw, indent=2))
        elif args.command == "epoch":
            r = client.epoch()
            print(json.dumps(r.raw, indent=2))
        elif args.command == "miners":
            for m in client.miners():
                print(f"{m.id}  score={m.score}  status={m.status}  wallet={m.wallet}")
        elif args.command == "balance":
            r = client.balance(args.wallet_id)
            print(f"{r.balance} {r.currency}")
        elif args.command == "attestation":
            r = client.attestation_status(args.miner_id)
            print(f"attested={r.attested}  epoch={r.epoch}  hw={r.hardware_hash}")
        elif args.command == "blocks":
            for b in client.explorer.blocks(args.limit):
                print(f"#{b.height}  {b.hash[:16]}...  miner={b.miner}  txs={b.tx_count}")
        elif args.command == "transactions":
            for t in client.explorer.transactions(args.limit):
                print(f"{t.tx_hash[:16]}...  {t.from_wallet}->{t.to_wallet}  {t.amount} RTC")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
