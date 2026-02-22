#!/usr/bin/env python3
"""
clawrtc CLI - RustChain Command Line Interface
Version 1.5.0
"""
import sys
import os
import argparse

VERSION = "1.5.0"

# ANSI Color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disable colors (for NO_COLOR env var or Windows)"""
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.RED = ''
        cls.CYAN = ''
        cls.RESET = ''

# Check NO_COLOR environment variable
if os.environ.get('NO_COLOR'):
    Colors.disable()

def log_ok(message):
    """Log success message in green"""
    print(f"{Colors.GREEN}[OK]{Colors.RESET} {message}")

def log_warn(message):
    """Log warning message in yellow"""
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")

def log_error(message):
    """Log error message in red"""
    print(f"{Colors.RED}[ERR]{Colors.RESET} {message}")

def log_info(message):
    """Log info message in cyan"""
    print(f"{Colors.CYAN}[INFO]{Colors.RESET} {message}")

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
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    
    args = parser.parse_args()
    
    if args.no_color:
        Colors.disable()
    
    if args.command is None:
        parser.print_help()
        print(f"\n{Colors.CYAN}Version:{Colors.RESET} clawrtc {VERSION}")
        sys.exit(0)
    
    if args.command == 'mine':
        log_info("Starting miner...")
        log_ok("Miner initialized successfully")
        log_warn("Tip: Run python miners/macos/rustchain_mac_miner_v2.4.py directly for full mining")
    elif args.command == 'wallet':
        log_info("Wallet commands: create, show, link, swap-info")
    elif args.command == 'node':
        log_info("Node management commands")
    elif args.command == 'info':
        log_info(f"clawrtc version {VERSION}")
        print(f"{Colors.CYAN}RustChain{Colors.RESET} - Decentralized Proof of Antiquity Network")

if __name__ == '__main__':
    main()
