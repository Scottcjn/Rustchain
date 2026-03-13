#!/usr/bin/env python3
"""
RustChain PS1 Bridge - PC Side Software

This program bridges the PS1 miner to the RustChain network via serial connection.
The PS1 sends attestation data over serial, and this bridge forwards it to the node.

Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
"""

import serial
import serial.tools.list_ports
import requests
import json
import time
import hashlib
import argparse
from datetime import datetime

# Configuration
DEFAULT_SERIAL_PORT = "COM3"  # Windows
DEFAULT_BAUD_RATE = 9600
NODE_URL = "https://rustchain.org"
WALLET_FILE = "ps1_wallet.json"

class PS1Bridge:
    def __init__(self, serial_port, baud_rate, wallet_name):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.wallet_name = wallet_name
        self.ser = None
        self.epoch_counter = 0
        self.last_attestation = None
        
    def connect(self):
        """Connect to PS1 via serial"""
        try:
            self.ser = serial.Serial(
                port=self.serial_port,
                baudrate=self.baud_rate,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            print(f"[BRIDGE] Connected to PS1 on {self.serial_port} @ {self.baud_rate} bps")
            return True
        except serial.SerialException as e:
            print(f"[BRIDGE] Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from PS1"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("[BRIDGE] Disconnected")
    
    def read_line(self):
        """Read a line from PS1"""
        try:
            line = b""
            while True:
                byte = self.ser.read(1)
                if not byte:
                    return None
                if byte == b'\n':
                    break
                line += byte
            return line.decode('ascii').strip()
        except Exception as e:
            print(f"[BRIDGE] Read error: {e}")
            return None
    
    def write_line(self, text):
        """Write a line to PS1"""
        try:
            self.ser.write((text + '\n').encode('ascii'))
            self.ser.flush()
        except Exception as e:
            print(f"[BRIDGE] Write error: {e}")
    
    def load_or_create_wallet(self):
        """Load existing wallet or create new one"""
        try:
            with open(WALLET_FILE, 'r') as f:
                data = json.load(f)
                wallet = data.get('wallet', self.wallet_name)
                print(f"[BRIDGE] Loaded wallet: {wallet}")
                return wallet
        except FileNotFoundError:
            wallet = self.wallet_name
            self.save_wallet(wallet)
            return wallet
    
    def save_wallet(self, wallet):
        """Save wallet to file"""
        with open(WALLET_FILE, 'w') as f:
            json.dump({
                'wallet': wallet,
                'created': datetime.now().isoformat(),
                'platform': 'PS1'
            }, f, indent=2)
        print(f"[BRIDGE] Saved wallet: {wallet}")
    
    def submit_attestation(self, attestation_data):
        """Submit attestation to RustChain node"""
        try:
            # Build payload
            payload = {
                "miner_pubkey": self.wallet_name,
                "miner_id": f"ps1-{self.wallet_name}",
                "device": {
                    "family": "retro_console",
                    "arch": "PS1",
                    "cpu": "MIPS R3000A",
                    "frequency_mhz": 33.87
                },
                "fingerprint": attestation_data,
                "epoch": self.epoch_counter
            }
            
            # Submit to node
            response = requests.post(
                f"{NODE_URL}/attest/submit",
                json=payload,
                verify=False,  # Self-signed cert
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"[BRIDGE] Attestation accepted! Reward: {result.get('reward', 0)} RTC")
                    return "OK"
                else:
                    print(f"[BRIDGE] Attestation rejected: {result.get('error', 'unknown')}")
                    return "FAIL"
            else:
                print(f"[BRIDGE] HTTP error: {response.status_code}")
                return "FAIL"
                
        except requests.RequestException as e:
            print(f"[BRIDGE] Network error: {e}")
            return "FAIL"
    
    def run(self):
        """Main bridge loop"""
        print("[BRIDGE] Starting PS1 Bridge...")
        print(f"[BRIDGE] Node: {NODE_URL}")
        print(f"[BRIDGE] Wallet: {self.wallet_name}")
        print("[BRIDGE] Press Ctrl+C to exit\n")
        
        # Load wallet
        self.load_or_create_wallet()
        
        # Main loop
        while True:
            try:
                # Read from PS1
                line = self.read_line()
                if not line:
                    time.sleep(0.1)
                    continue
                
                print(f"[PS1] <- {line}")
                
                # Parse PS1 message
                if line.startswith("ATTEST:"):
                    # Extract attestation JSON
                    attestation_json = line[7:]
                    try:
                        attestation_data = json.loads(attestation_json)
                        
                        # Submit to node
                        result = self.submit_attestation(attestation_data)
                        
                        # Send result back to PS1
                        self.write_line(f"RESULT:{result}")
                        print(f"[BRIDGE] -> RESULT:{result}")
                        
                        if result == "OK":
                            self.last_attestation = datetime.now()
                            self.epoch_counter += 1
                            
                    except json.JSONDecodeError as e:
                        print(f"[BRIDGE] Invalid JSON from PS1: {e}")
                        self.write_line("RESULT:INVALID_JSON")
                
                elif line.startswith("STATUS:"):
                    # PS1 requesting status
                    status = {
                        "epoch": self.epoch_counter,
                        "last_attestation": self.last_attestation.isoformat() if self.last_attestation else None,
                        "node_status": "online"
                    }
                    self.write_line(f"STATUS:{json.dumps(status)}")
                
            except KeyboardInterrupt:
                print("\n[BRIDGE] Exiting...")
                break
            except Exception as e:
                print(f"[BRIDGE] Error: {e}")
                time.sleep(1)
        
        self.disconnect()


def list_serial_ports():
    """List available serial ports"""
    ports = serial.tools.list_ports.comports()
    print("\nAvailable serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")
    print()


def main():
    parser = argparse.ArgumentParser(description='RustChain PS1 Bridge')
    parser.add_argument('-p', '--port', default=DEFAULT_SERIAL_PORT,
                       help=f'Serial port (default: {DEFAULT_SERIAL_PORT})')
    parser.add_argument('-b', '--baud', type=int, default=DEFAULT_BAUD_RATE,
                       help=f'Baud rate (default: {DEFAULT_BAUD_RATE})')
    parser.add_argument('-w', '--wallet', default='ps1-miner',
                       help='Wallet name')
    parser.add_argument('--list-ports', action='store_true',
                       help='List available serial ports')
    
    args = parser.parse_args()
    
    if args.list_ports:
        list_serial_ports()
        return
    
    # Create and run bridge
    bridge = PS1Bridge(args.port, args.baud, args.wallet)
    
    if not bridge.connect():
        print("\nFailed to connect. Use --list-ports to see available ports.")
        return
    
    try:
        bridge.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        bridge.disconnect()


if __name__ == "__main__":
    main()
