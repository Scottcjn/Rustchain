#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Witness CLI — Write, Read, and Verify epoch proofs.

Usage:
    rustchain-witness write --epoch 500 --output witness.img
    rustchain-witness read --input witness.img
    rustchain-witness verify witness.json
    rustchain-witness qr --epoch 500 --output witness.png
"""

import argparse
import json
import sys
from pathlib import Path

from witness_format import (
    EpochWitness,
    MinerEntry,
    write_witnesses_to_image,
    read_witnesses_from_image,
    verify_witness,
    witnesses_per_disk,
    FLOPPY_SIZE,
    ZIP_DISK_SIZE,
)


def cmd_write(args):
    """Write witnesses to a floppy image."""
    # Load witnesses from JSON file or generate sample
    if args.from_json:
        data = json.loads(Path(args.from_json).read_text())
        if isinstance(data, list):
            witnesses = [EpochWitness.from_dict(d) for d in data]
        else:
            witnesses = [EpochWitness.from_dict(data)]
    else:
        # Generate a sample witness for the given epoch
        witnesses = [EpochWitness(
            epoch=args.epoch,
            timestamp=int(__import__("time").time()),
            settlement_hash="a" * 64,
            ergo_anchor_txid="b" * 64,
            commitment_hash="c" * 64,
            miners=[MinerEntry("miner-1", "G4", 2.5)],
        )]

    size = FLOPPY_SIZE if args.format == "floppy" else ZIP_DISK_SIZE
    ok, msg = write_witnesses_to_image(witnesses, args.output, image_size=size)
    print(msg)
    return 0 if ok else 1


def cmd_read(args):
    """Read witnesses from a floppy image."""
    witnesses = read_witnesses_from_image(args.input)
    print(f"Found {len(witnesses)} epoch witnesses:\n")
    for w in witnesses:
        print(f"  Epoch {w.epoch} | {len(w.miners)} miners | "
              f"Settlement: {w.settlement_hash[:16]}...")
    return 0


def cmd_verify(args):
    """Verify a witness file."""
    data = json.loads(Path(args.file).read_text())
    witness = EpochWitness.from_dict(data)
    ok, msg = verify_witness(witness, node_url=args.node or "")
    print(msg)
    return 0 if ok else 1


def cmd_info(args):
    """Show capacity info for different media."""
    for name, size in [("1.44MB Floppy", FLOPPY_SIZE), ("100MB ZIP Disk", ZIP_DISK_SIZE)]:
        cap = witnesses_per_disk(size)
        print(f"{name}: ~{cap:,} epoch witnesses")


def main():
    parser = argparse.ArgumentParser(
        prog="rustchain-witness",
        description="RustChain Floppy Witness Kit — Epoch Proofs on Old Media",
    )
    sub = parser.add_subparsers(dest="command")

    # Write
    p_write = sub.add_parser("write", help="Write witnesses to disk image")
    p_write.add_argument("--epoch", type=int, default=1, help="Epoch number")
    p_write.add_argument("--output", "-o", default="witness.img", help="Output image path")
    p_write.add_argument("--from-json", help="Load witnesses from JSON file")
    p_write.add_argument("--format", choices=["floppy", "zip"], default="floppy")

    # Read
    p_read = sub.add_parser("read", help="Read witnesses from disk image")
    p_read.add_argument("--input", "-i", required=True, help="Input image path")

    # Verify
    p_verify = sub.add_parser("verify", help="Verify a witness file")
    p_verify.add_argument("file", help="Witness JSON file")
    p_verify.add_argument("--node", help="Node URL for online verification")

    # Info
    sub.add_parser("info", help="Show media capacity info")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    commands = {"write": cmd_write, "read": cmd_read, "verify": cmd_verify, "info": cmd_info}
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
