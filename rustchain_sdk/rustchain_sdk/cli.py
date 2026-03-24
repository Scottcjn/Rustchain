# -*- coding: utf-8 -*-
"""
RustChain Python SDK - CLI Wrapper
Usage:
    rustchain balance <wallet_id>
    rustchain transfer <from> <to> <amount>
    rustchain epoch
    rustchain miners
    rustchain health
"""
from __future__ import annotations
import asyncio, sys, json, hashlib
from .client import RustChainClient
from .exceptions import RustChainError

def main():
    if len(sys.argv) < 2:
        print("Usage: rustchain <command> [args]")
        print("Commands: health, balance, transfer, epoch, miners, block, tx")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    try:
        if cmd == "balance" and len(args) >= 1:
            wallet_id = args[0]
            asyncio.run(_balance(wallet_id))
        elif cmd == "transfer" and len(args) >= 3:
            asyncio.run(_transfer(args[0], args[1], float(args[2])))
        elif cmd == "epoch":
            asyncio.run(_epoch())
        elif cmd == "miners":
            limit = int(args[0]) if args else 20
            asyncio.run(_miners(limit))
        elif cmd == "health":
            asyncio.run(_health())
        elif cmd == "block" and args:
            asyncio.run(_block(int(args[0])))
        elif cmd == "tx" and args:
            asyncio.run(_tx(args[0]))
        elif cmd == "attest" and args:
            asyncio.run(_attest(args[0]))
        else:
            print(f"Unknown command: {cmd} with args: {args}")
            sys.exit(1)
    except RustChainError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

async def _balance(wallet_id: str):
    async with RustChainClient() as client:
        result = await client.balance(wallet_id)
        print(json.dumps(result, indent=2))

async def _transfer(from_w: str, to_w: str, amount: float):
    async with RustChainClient() as client:
        unsigned = await client.transfer_unsigned(from_w, to_w, amount)
        print("Unsigned transfer created. Sign with your wallet:")
        print(json.dumps(unsigned, indent=2))

async def _epoch():
    async with RustChainClient() as client:
        result = await client.epoch()
        print(json.dumps(result, indent=2))

async def _miners(limit: int):
    async with RustChainClient() as client:
        miners = await client.miners(limit=limit)
        for m in miners:
            score = m.get("attestation_score", 0)
            print(f"  {m['miner_id'][:16]:16s} | {m.get('architecture','?'):12s} | score={score:.2f}")

async def _health():
    async with RustChainClient() as client:
        result = await client.health()
        print(json.dumps(result, indent=2))

async def _block(n: int):
    async with RustChainClient() as client:
        result = await client.explorer_block(n)
        print(json.dumps(result, indent=2))

async def _tx(h: str):
    async with RustChainClient() as client:
        result = await client.explorer_tx(h)
        print(json.dumps(result, indent=2))

async def _attest(miner_id: str):
    async with RustChainClient() as client:
        result = await client.attestation_status(miner_id)
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
