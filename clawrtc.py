#!/usr/bin/env python3
"""
clawrtc CLI - RustChain Command Line Interface
Version 1.5.0
"""
import sys
import argparse

VERSION = "1.5.0"

def main():
    parser = argparse.ArgumentParser(
        prog='clawrtc',
        description='RustChain CLI Tool - Mining, Wallet, and Node Management'
    )
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'clawrtc {VERSION}'
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['mine', 'wallet', 'node', 'info'],
        help='Command to execute'
    )
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        print(f"\nVersion: clawrtc {VERSION}")
        sys.exit(0)
    
    if args.command == 'mine':
        print("Starting miner...")
        print("Tip: Run python miners/macos/rustchain_mac_miner_v2.4.py directly")
    elif args.command == 'wallet':
        print("Wallet commands: create, show, link, swap-info")
    elif args.command == 'node':
        print("Node management commands")
    elif args.command == 'info':
        print(f"clawrtc version {VERSION}")
        print("RustChain - Decentralized Proof of Antiquity Network")

if __name__ == '__main__':
    main()
