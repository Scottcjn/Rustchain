"""RustChain CLI - Command-line interface for RustChain SDK."""
import argparse
import asyncio
import json
import sys

from .client import RustChainClient
from .models import SignedTransfer
from .exceptions import RustChainError


async def cmd_health(args) -> int:
    """Show node health."""
    async with RustChainClient() as client:
        health = await client.get_health()
        print(json.dumps({
            "ok": health.ok,
            "version": health.version,
            "uptime_s": health.uptime_s,
            "db_rw": health.db_rw,
            "tip_age_slots": health.tip_age_slots,
            "backup_age_hours": health.backup_age_hours,
        }, indent=2))
    return 0


async def cmd_epoch(args) -> int:
    """Show current epoch."""
    async with RustChainClient() as client:
        epoch = await client.get_epoch()
        print(json.dumps({
            "epoch": epoch.epoch,
            "slot": epoch.slot,
            "blocks_per_epoch": epoch.blocks_per_epoch,
            "epoch_pot": epoch.epoch_pot,
            "enrolled_miners": epoch.enrolled_miners,
        }, indent=2))
    return 0


async def cmd_miners(args) -> int:
    """List all miners."""
    async with RustChainClient() as client:
        miners = await client.get_miners()
        for m in miners:
            print(json.dumps({
                "miner": m.miner,
                "device_arch": m.device_arch,
                "device_family": m.device_family,
                "hardware_type": m.hardware_type,
                "antiquity_multiplier": m.antiquity_multiplier,
                "last_attest": m.last_attest,
            }))
    return 0


async def cmd_balance(args) -> int:
    """Show miner balance."""
    async with RustChainClient() as client:
        bal = await client.get_balance(args.miner_id)
        print(json.dumps({
            "ok": bal.ok,
            "miner_id": bal.miner_id,
            "amount_rtc": bal.amount_rtc,
            "amount_i64": bal.amount_i64,
        }, indent=2))
    return 0


async def cmd_transfer_signed(args) -> int:
    """Submit a signed transfer."""
    tx = SignedTransfer(
        from_address=args.from_addr,
        to_address=args.to_addr,
        amount_rtc=args.amount,
        nonce=args.nonce,
        signature=args.signature,
        public_key=args.pubkey,
    )
    async with RustChainClient() as client:
        result = await client.submit_transfer_signed(tx)
        print(json.dumps(result, indent=2))
    return 0


async def cmd_admin_transfer(args) -> int:
    """Submit an admin transfer."""
    async with RustChainClient() as client:
        result = await client.admin_transfer(
            admin_key=args.admin_key,
            from_miner=args.from_miner,
            to_miner=args.to_miner,
            amount_rtc=args.amount,
        )
        print(json.dumps(result, indent=2))
    return 0


async def cmd_settle(args) -> int:
    """Settle rewards (admin)."""
    async with RustChainClient() as client:
        result = await client.settle_rewards(admin_key=args.admin_key)
        print(json.dumps(result, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="rustchain",
        description="RustChain Python SDK CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Show node health status")
    sub.add_parser("epoch", help="Show current epoch info")
    sub.add_parser("miners", help="List all miners")

    p_bal = sub.add_parser("balance", help="Show miner balance")
    p_bal.add_argument("miner_id", help="Miner ID or name")

    p_tx = sub.add_parser("transfer-signed", help="Submit a signed transfer")
    p_tx.add_argument("--from", dest="from_addr", required=True, help="From address")
    p_tx.add_argument("--to", dest="to_addr", required=True, help="To address")
    p_tx.add_argument("--amount", type=float, required=True, help="Amount in RTC")
    p_tx.add_argument("--nonce", type=int, required=True, help="Transaction nonce")
    p_tx.add_argument("--signature", required=True, help="Transaction signature")
    p_tx.add_argument("--pubkey", required=True, help="Public key")

    p_admin = sub.add_parser("admin-transfer", help="Submit an admin transfer")
    p_admin.add_argument("--admin-key", required=True, help="Admin API key")
    p_admin.add_argument("--from", dest="from_miner", required=True, help="From miner")
    p_admin.add_argument("--to", dest="to_miner", required=True, help="To miner")
    p_admin.add_argument("--amount", type=float, required=True, help="Amount in RTC")

    p_settle = sub.add_parser("settle", help="Settle rewards (admin)")
    p_settle.add_argument("--admin-key", required=True, help="Admin API key")

    args = parser.parse_args()

    commands = {
        "health": cmd_health,
        "epoch": cmd_epoch,
        "miners": cmd_miners,
        "balance": cmd_balance,
        "transfer-signed": cmd_transfer_signed,
        "admin-transfer": cmd_admin_transfer,
        "settle": cmd_settle,
    }

    try:
        return asyncio.run(commands[args.command](args))
    except RustChainError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
