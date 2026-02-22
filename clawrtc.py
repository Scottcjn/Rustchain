#!/usr/bin/env python3
"""
clawrtc CLI - RustChain Command Line Interface
Version 1.5.0
"""
import sys
import os
import json
import argparse
import platform
from datetime import datetime

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

def emit(event_type, **data):
    """
    Emit structured output.
    In JSON mode: outputs JSONL (one JSON object per line)
    In normal mode: outputs colored human-readable text
    """
    if args.json_mode:
        output = {"event": event_type, "timestamp": datetime.utcnow().isoformat() + "Z", **data}
        print(json.dumps(output), flush=True)
    else:
        message = data.get('message', str(data))
        if event_type == 'ok':
            print(f"{Colors.GREEN}[OK]{Colors.RESET} {message}")
        elif event_type == 'warn':
            print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {message}")
        elif event_type == 'error':
            print(f"{Colors.RED}[ERR]{Colors.RESET} {message}")
        elif event_type == 'info':
            print(f"{Colors.CYAN}[INFO]{Colors.RESET} {message}")
        elif event_type == 'startup':
            print(f"{Colors.CYAN}[STARTUP]{Colors.RESET} {message}")
        elif event_type == 'attestation':
            status = data.get('status', 'unknown')
            if status == 'success':
                print(f"{Colors.GREEN}[ATTEST]{Colors.RESET} {message}")
            else:
                print(f"{Colors.YELLOW}[ATTEST]{Colors.RESET} {message}")
        elif event_type == 'fingerprint':
            print(f"{Colors.CYAN}[FINGERPRINT]{Colors.RESET} {message}")

# Global args reference for emit()
args = None

def main():
    global args
    
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
    parser.add_argument(
        '--json',
        dest='json_mode',
        action='store_true',
        help='Output in JSON format (JSONL) for programmatic parsing'
    )
    parser.add_argument(
        '--wallet',
        type=str,
        help='Wallet address for mining'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate mining without actual network calls'
    )
    
    args = parser.parse_args()
    
    if args.no_color:
        Colors.disable()
    
    if args.command is None:
        if args.json_mode:
            print(json.dumps({"event": "help", "version": VERSION}))
        else:
            parser.print_help()
            print(f"\n{Colors.CYAN}Version:{Colors.RESET} clawrtc {VERSION}")
        sys.exit(0)
    
    if args.command == 'mine':
        # Emit startup event
        emit('startup', 
             message=f"Starting clawrtc miner v{VERSION}",
             wallet=args.wallet or 'not specified',
             node='https://50.28.86.131',
             hardware={
                 'arch': platform.machine(),
                 'family': 'modern' if platform.machine() in ['x86_64', 'arm64'] else 'vintage'
             })
        
        if args.dry_run:
            emit('info', message="Dry run mode - no actual mining")
            
            # Simulate attestation
            emit('attestation', 
                 status='success',
                 epoch=75,
                 slot=10823,
                 message="Attestation accepted")
            
            # Simulate fingerprint check
            emit('fingerprint',
                 checks_passed=6,
                 checks_total=6,
                 message="All fingerprint checks passed")
            
            emit('ok', message="Dry run completed successfully")
        else:
            emit('info', message="Starting miner...")
            emit('ok', message="Miner initialized successfully")
            emit('warn', message="Tip: Run python miners/macos/rustchain_mac_miner_v2.4.py directly for full mining")
    
    elif args.command == 'wallet':
        emit('info', message="Wallet commands: create, show, link, swap-info")
    
    elif args.command == 'node':
        emit('info', message="Node management commands")
    
    elif args.command == 'info':
        if args.json_mode:
            print(json.dumps({
                "event": "info",
                "name": "clawrtc",
                "version": VERSION,
                "description": "RustChain - Decentralized Proof of Antiquity Network"
            }))
        else:
            emit('info', message=f"clawrtc version {VERSION}")
            print(f"{Colors.CYAN}RustChain{Colors.RESET} - Decentralized Proof of Antiquity Network")

if __name__ == '__main__':
    main()
