#!/usr/bin/env python3
"""
RustChain Game Boy Color Bridge
Host software for GBC miner communication via GB Link Cable USB adapter.

Bounty #432 - Port Miner to Game Boy Color (100 RTC)
Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b
"""

import serial
import serial.tools.list_ports
import json
import time
import hashlib
import requests
import argparse
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# RustChain API endpoint
RUSTCHAIN_API = "https://rustchain.org"

class GBCBridge:
    """Bridge between Game Boy Color and RustChain network."""
    
    def __init__(self, port: str, wallet: str, baud_rate: int = 9600):
        self.port = port
        self.wallet = wallet
        self.baud_rate = baud_rate
        self.ser: Optional[serial.Serial] = None
        self.hardware_id: Optional[str] = None
        self.epoch_count = 0
        self.running = False
        
    def connect(self) -> bool:
        """Connect to GBC via serial port."""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1.0
            )
            print(f"✓ Connected to GBC on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from GBC."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("✓ Disconnected from GBC")
    
    def send_command(self, command: str) -> Optional[str]:
        """Send command to GBC and receive response."""
        if not self.ser or not self.ser.is_open:
            return None
        
        try:
            # Send command with newline
            self.ser.write(f"{command}\n".encode('ascii'))
            self.ser.flush()
            
            # Wait for response
            time.sleep(0.5)
            
            if self.ser.in_waiting > 0:
                response = self.ser.readline().decode('ascii').strip()
                return response
            return None
        except Exception as e:
            print(f"Communication error: {e}")
            return None
    
    def get_hardware_id(self) -> Optional[str]:
        """Request hardware ID from GBC."""
        response = self.send_command("GETID")
        if response and response.startswith("OK|"):
            parts = response.split("|")
            if len(parts) >= 2:
                self.hardware_id = parts[1]
                return self.hardware_id
        return None
    
    def request_attestation(self) -> Optional[Dict[str, Any]]:
        """Request attestation data from GBC."""
        nonce = int(time.time())
        command = f"ATTEST|{self.wallet}|{nonce}"
        
        response = self.send_command(command)
        if not response or not response.startswith("OK|"):
            return None
        
        try:
            # Parse response: OK|hardware_id|signature|timestamp|fingerprint_data
            parts = response.split("|")
            if len(parts) < 5:
                return None
            
            attestation = {
                "hardware_id": parts[1],
                "signature": parts[2],
                "timestamp": int(parts[3]),
                "fingerprint_data": json.loads(parts[4]) if len(parts) > 4 else {}
            }
            
            return attestation
        except Exception as e:
            print(f"Failed to parse attestation: {e}")
            return None
    
    def submit_attestation(self, attestation: Dict[str, Any]) -> bool:
        """Submit attestation to RustChain network."""
        try:
            url = f"{RUSTCHAIN_API}/attest"
            payload = {
                "wallet": self.wallet,
                "hardware_id": attestation["hardware_id"],
                "signature": attestation["signature"],
                "timestamp": attestation["timestamp"],
                "fingerprint_data": attestation["fingerprint_data"],
                "device_type": "gameboy_color",
                "device_year": 1998,
                "antiquity_multiplier": 2.6
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    print(f"✓ Attestation accepted! Epoch: {result.get('epoch', '?')}")
                    return True
                else:
                    print(f"✗ Attestation rejected: {result.get('error', 'Unknown error')}")
            else:
                print(f"✗ API error: {response.status_code}")
            
            return False
        except requests.RequestException as e:
            print(f"✗ Network error: {e}")
            return False
    
    def check_balance(self) -> Optional[float]:
        """Check wallet balance."""
        try:
            url = f"{RUSTCHAIN_API}/wallet/balance?miner_id={self.wallet}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("balance", 0.0)
        except:
            pass
        return None
    
    def run_mining_loop(self):
        """Main mining loop."""
        print(f"\n🎮 Starting GBC Mining Loop...")
        print(f"   Wallet: {self.wallet}")
        print(f"   Device: Game Boy Color (1998)")
        print(f"   Multiplier: 2.6×")
        print(f"   Press Ctrl+C to stop\n")
        
        self.running = True
        last_attestation = 0
        attestation_interval = 600  # 10 minutes (1 epoch)
        
        try:
            while self.running:
                current_time = time.time()
                
                # Check if it's time for attestation
                if current_time - last_attestation >= attestation_interval:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Requesting attestation...")
                    
                    attestation = self.request_attestation()
                    if attestation:
                        if self.submit_attestation(attestation):
                            self.epoch_count += 1
                            last_attestation = current_time
                            
                            # Show earnings estimate
                            estimated = self.epoch_count * 0.31  # 0.31 RTC/epoch with 2.6×
                            print(f"   Epochs mined: {self.epoch_count}")
                            print(f"   Estimated earnings: {estimated:.2f} RTC")
                    else:
                        print("   ✗ Failed to get attestation from GBC")
                
                # Update display status
                self.send_command(f"STATUS|{self.epoch_count}")
                
                # Wait
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n\n⏹ Stopping mining...")
            self.running = False
    
    def run_diagnostics(self):
        """Run hardware diagnostics."""
        print("\n🔍 Running GBC Diagnostics...\n")
        
        # Check connection
        print("1. Connection Test")
        response = self.send_command("PING")
        if response:
            print(f"   ✓ GBC responded: {response}")
        else:
            print("   ✗ No response from GBC")
            return
        
        # Get hardware ID
        print("\n2. Hardware ID")
        hw_id = self.get_hardware_id()
        if hw_id:
            print(f"   ✓ Hardware ID: {hw_id}")
        else:
            print("   ✗ Failed to get hardware ID")
        
        # Run fingerprint checks
        print("\n3. Fingerprint Checks")
        response = self.send_command("FPCHECK")
        if response and response.startswith("OK|"):
            print(f"   ✓ All checks passed")
            print(f"   {response}")
        else:
            print(f"   ✗ Fingerprint check failed")
        
        # Check emulator detection
        print("\n4. Emulator Detection")
        response = self.send_command("EMUCHECK")
        if response:
            if "REAL" in response:
                print(f"   ✓ Real hardware detected")
            elif "EMU" in response:
                print(f"   ⚠ Emulator detected (rewards will be minimal)")
            else:
                print(f"   ? Unknown: {response}")
        
        print("\n✓ Diagnostics complete\n")


def list_serial_ports():
    """List available serial ports."""
    print("\nAvailable serial ports:")
    ports = serial.tools.list_ports.comports()
    for port in ports:
        print(f"  {port.device} - {port.description}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="RustChain GBC Bridge - Mine RTC on Game Boy Color"
    )
    parser.add_argument(
        "--port", "-p",
        required=True,
        help="Serial port (e.g., COM3, /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--wallet", "-w",
        required=True,
        help="RustChain wallet address"
    )
    parser.add_argument(
        "--baud", "-b",
        type=int,
        default=9600,
        help="Baud rate (default: 9600)"
    )
    parser.add_argument(
        "--list-ports", "-l",
        action="store_true",
        help="List available serial ports"
    )
    parser.add_argument(
        "--diagnose", "-d",
        action="store_true",
        help="Run diagnostics and exit"
    )
    
    args = parser.parse_args()
    
    if args.list_ports:
        list_serial_ports()
        return
    
    # Create bridge
    bridge = GBCBridge(args.port, args.wallet, args.baud)
    
    # Connect
    if not bridge.connect():
        print("\nTroubleshooting:")
        print("  1. Check GBC is powered on")
        print("  2. Verify link cable is connected")
        print("  3. Try a different USB port")
        print("  4. Use --list-ports to see available ports\n")
        sys.exit(1)
    
    try:
        if args.diagnose:
            bridge.run_diagnostics()
        else:
            bridge.run_mining_loop()
    finally:
        bridge.disconnect()


if __name__ == "__main__":
    main()
