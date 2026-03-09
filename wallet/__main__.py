#!/usr/bin/env python3
"""
ClawRTC Wallet CLI — Command-Line Wallet Manager

Main entry point for `clawrtc wallet` commands.

Usage:
    python -m wallet coinbase show
    python -m wallet coinbase create
    python -m wallet coinbase link 0xYourAddress
    python -m wallet coinbase swap-info

Or install clawrtc package and run:
    clawrtc wallet coinbase show
"""

import argparse
import sys

from coinbase_wallet import cmd_coinbase


def main():
    parser = argparse.ArgumentParser(
        description="ClawRTC Wallet CLI - Coinbase Wallet Manager",
        prog="clawrtc wallet"
    )

    subparsers = parser.add_subparsers(dest="wallet_command", help="Wallet commands")

    # coinbase subcommand
    coinbase_parser = subparsers.add_parser("coinbase", help="Coinbase Base wallet operations")
    coinbase_subparsers = coinbase_parser.add_subparsers(dest="coinbase_action", help="Coinbase actions")

    coinbase_subparsers.add_parser("create", help="Create a new Coinbase Base wallet")
    coinbase_subparsers.add_parser("show", help="Show Coinbase Base wallet info")
    coinbase_subparsers.add_parser("swap-info", help="Show USDC→wRTC swap instructions")

    link_parser = coinbase_subparsers.add_parser("link", help="Link an existing Base address")
    link_parser.add_argument("base_address", help="Base network address (0x...)")

    args = parser.parse_args()

    if args.wallet_command == "coinbase":
        cmd_coinbase(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
