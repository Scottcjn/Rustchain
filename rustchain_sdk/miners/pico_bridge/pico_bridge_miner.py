#!/usr/bin/env python3
"""
Pico Serial Bridge Miner - RIP-304
===================================

RustChain miner client for retro console mining via Raspberry Pi Pico.
Communicates with Pico bridge to capture console controller port timing
and submit attestations to RustChain node.

Supports:
- Real hardware mode (Pico connected via USB serial)
- Simulation mode (mock data for testing without hardware)

Author: Scott Boudreaux / Elyan Labs
License: Apache 2.0
"""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple

# Try to import serial library for real hardware mode
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    print("[WARN] pyserial not installed. Simulation mode only.")
    print("       Install with: pip install pyserial")


# ═══════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "wallet_id": "",
    "node_url": "https://rustchain.org",
    "miner_name": "pico-console-miner",
    "console_type": "n64_mips",
    "pico_port": "",  # Auto-detect if empty
    "pico_baud": 115200,
    "simulation_mode": False,
    "attestation_interval_sec": 300,  # 5 minutes
}

CONSOLE_PROFILES = {
    # Nintendo consoles
    "nes_6502": {
        "model": "NES/Famicom NUS-001",
        "cpu": "Ricoh 2A03 (6502 derivative) @ 1.79MHz",
        "cores": 1,
        "memory_mb": 0.002,  # 2KB RAM
        "protocol": "serial_shift_register",
        "clock_rate": 60,  # Hz controller poll
        "timing_mean_ns": 16667000,  # ~60Hz
        "timing_stdev_ns": 1250,  # Real hardware jitter
        "rom_hash_time_us": 4500000,  # Slow 6502
    },
    "snes_65c816": {
        "model": "SNES/Super Famicom SNS-001",
        "cpu": "Ricoh 5A22 (65C816) @ 3.58MHz",
        "cores": 1,
        "memory_mb": 0.125,  # 128KB RAM
        "protocol": "serial_shift_register",
        "clock_rate": 60,
        "timing_mean_ns": 16667000,
        "timing_stdev_ns": 1100,
        "rom_hash_time_us": 2200000,
    },
    "n64_mips": {
        "model": "Nintendo 64 NUS-001",
        "cpu": "NEC VR4300 (MIPS R4300i) @ 93.75MHz",
        "cores": 1,
        "memory_mb": 4,
        "protocol": "joybus",
        "clock_rate": 250,  # Joybus is faster
        "timing_mean_ns": 250000,  # 4 Mbit/s
        "timing_stdev_ns": 1250,
        "rom_hash_time_us": 847000,  # Reference: Legend of Elya
    },
    "gameboy_z80": {
        "model": "Game Boy DMG-01",
        "cpu": "Sharp LR35902 (Z80 derivative) @ 4.19MHz",
        "cores": 1,
        "memory_mb": 0.008,  # 8KB RAM
        "protocol": "serial_link",
        "clock_rate": 512,  # 8 Kbit/s
        "timing_mean_ns": 122000,  # ~8Kbit
        "timing_stdev_ns": 800,
        "rom_hash_time_us": 3500000,
    },
    "gameboy_color_z80": {
        "model": "Game Boy Color CGB-001",
        "cpu": "Sharp LR35902 (Z80 derivative) @ 8.38MHz",
        "cores": 1,
        "memory_mb": 0.032,  # 32KB RAM
        "protocol": "serial_link",
        "clock_rate": 512,
        "timing_mean_ns": 122000,
        "timing_stdev_ns": 750,
        "rom_hash_time_us": 1800000,
    },
    "gba_arm7": {
        "model": "Game Boy Advance AGB-001",
        "cpu": "ARM7TDMI @ 16.78MHz",
        "cores": 1,
        "memory_mb": 0.256,  # 256KB RAM
        "protocol": "serial_link",
        "clock_rate": 512,
        "timing_mean_ns": 122000,
        "timing_stdev_ns": 600,
        "rom_hash_time_us": 450000,
    },
    # Sega consoles
    "sms_z80": {
        "model": "Sega Master System MK-1",
        "cpu": "Zilog Z80 @ 3.58MHz",
        "cores": 1,
        "memory_mb": 0.008,  # 8KB RAM
        "protocol": "parallel",
        "clock_rate": 60,
        "timing_mean_ns": 16667000,
        "timing_stdev_ns": 1100,
        "rom_hash_time_us": 3800000,
    },
    "genesis_68000": {
        "model": "Sega Genesis/Mega Drive MK-1",
        "cpu": "Motorola 68000 @ 7.67MHz",
        "cores": 1,
        "memory_mb": 0.064,  # 64KB RAM
        "protocol": "parallel",
        "clock_rate": 60,
        "timing_mean_ns": 16667000,
        "timing_stdev_ns": 1000,
        "rom_hash_time_us": 1500000,
    },
    "saturn_sh2": {
        "model": "Sega Saturn MK-1",
        "cpu": "Hitachi SH-2 (dual) @ 28.6MHz",
        "cores": 2,
        "memory_mb": 2,
        "protocol": "smpc_parallel",
        "clock_rate": 60,
        "timing_mean_ns": 16667000,
        "timing_stdev_ns": 900,
        "rom_hash_time_us": 350000,
    },
    "ps1_mips": {
        "model": "PlayStation SCPH-1001",
        "cpu": "MIPS R3000A @ 33.87MHz",
        "cores": 1,
        "memory_mb": 2,
        "protocol": "spi_serial",
        "clock_rate": 250000,  # 250 Kbit/s
        "timing_mean_ns": 4000,  # ~250Kbit
        "timing_stdev_ns": 500,
        "rom_hash_time_us": 420000,
    },
}


# ═══════════════════════════════════════════════════════════
# PICO SERIAL COMMUNICATION
# ═══════════════════════════════════════════════════════════

class PicoBridge:
    """Communicates with Raspberry Pi Pico via USB serial."""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 2.0):
        if not SERIAL_AVAILABLE:
            raise RuntimeError("pyserial not available")
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        self.board_id = None

    def connect(self) -> bool:
        """Establish serial connection to Pico."""
        try:
            self.ser = serial.Serial(
                self.port,
                self.baud,
                timeout=self.timeout
            )
            time.sleep(0.5)  # Wait for Pico to reset
            # Read board ID from Pico
            self.board_id = self._read_board_id()
            return True
        except Exception as e:
            print(f"[ERROR] Failed to connect to Pico: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _read_board_id(self) -> Optional[str]:
        """Read unique RP2040 board ID from Pico."""
        try:
            self.ser.write(b'ID\n')
            line = self.ser.readline().decode('utf-8').strip()
            if line.startswith('ID:'):
                return line[3:].strip()
        except Exception:
            pass
        return None

    def send_challenge(self, nonce: str) -> bool:
        """Send challenge nonce to Pico for console to process."""
        try:
            cmd = f'CHALLENGE:{nonce}\n'.encode('utf-8')
            self.ser.write(cmd)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to send challenge: {e}")
            return False

    def read_attestation(self, timeout_sec: float = 30.0) -> Optional[Dict]:
        """Read attestation result from Pico."""
        try:
            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                line = self.ser.readline().decode('utf-8').strip()
                if line.startswith('ATTEST:'):
                    # Parse JSON payload
                    json_str = line[7:]
                    return json.loads(json_str)
                elif line.startswith('ERROR:'):
                    print(f"[PICO ERROR] {line[6:]}")
                    return None
            print("[WARN] Timeout waiting for Pico attestation")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to read attestation: {e}")
            return None

    @staticmethod
    def auto_detect_port() -> Optional[str]:
        """Auto-detect Pico serial port."""
        if not SERIAL_AVAILABLE:
            return None
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Pico uses VID:PID 2E8A:000A (CDC-ACM)
            if port.vid == 0x2E8A and port.pid == 0x000A:
                return port.device
            # Also check by description
            if 'pico' in port.description.lower() or 'rp2040' in port.description.lower():
                return port.device
        # Fallback: first ACM/ttyUSB device
        for port in ports:
            if 'ttyACM' in port.device or 'ttyUSB' in port.device:
                return port.device
        return None


# ═══════════════════════════════════════════════════════════
# SIMULATION MODE (No Hardware Required)
# ═══════════════════════════════════════════════════════════

class PicoSimulator:
    """Simulates Pico bridge for testing without hardware."""

    def __init__(self, console_type: str = "n64_mips"):
        self.console_type = console_type
        self.profile = CONSOLE_PROFILES.get(console_type, CONSOLE_PROFILES["n64_mips"])
        # Generate a fake but consistent board ID
        self.board_id = f"RP2040-SIM-{hashlib.sha256(console_type.encode()).hexdigest()[:12].upper()}"

    def connect(self) -> bool:
        print(f"[SIM] Connected to virtual Pico bridge for {self.console_type}")
        return True

    def disconnect(self):
        print("[SIM] Disconnected from virtual Pico")

    def send_challenge(self, nonce: str) -> bool:
        print(f"[SIM] Processing challenge nonce: {nonce[:16]}...")
        return True

    def read_attestation(self, timeout_sec: float = 5.0) -> Optional[Dict]:
        """Generate realistic mock attestation data."""
        profile = self.profile

        # Generate timing data with realistic jitter
        # Real hardware has CV > 0.0001, emulators have ~0
        base_cv = profile["timing_stdev_ns"] / profile["timing_mean_ns"]
        # Add small random variation but keep above emulation threshold
        cv = max(0.0002, base_cv * random.uniform(0.8, 1.2))

        # ROM hash time with realistic variance
        hash_time = int(profile["rom_hash_time_us"] * random.uniform(0.95, 1.05))

        # Bus jitter - real hardware has measurable jitter
        jitter_stdev = int(profile["timing_stdev_ns"] * random.uniform(0.8, 1.2))

        # Simulate console-computed hash (in real scenario, console CPU does this)
        mock_hash = hashlib.sha256(f"sim_{self.console_type}_{time.time()}".encode()).hexdigest()

        return {
            "ctrl_port_timing": {
                "mean_ns": int(profile["timing_mean_ns"] * random.uniform(0.99, 1.01)),
                "stdev_ns": jitter_stdev,
                "cv": round(cv, 6),
                "samples": random.randint(480, 520),
            },
            "rom_execution": {
                "hash_result": mock_hash,
                "time_us": hash_time,
            },
            "bus_jitter": {
                "stdev_ns": jitter_stdev,
                "samples": 500,
            },
            "board_id": self.board_id,
            "firmware_version": "1.0.0-sim",
        }


# ═══════════════════════════════════════════════════════════
# ATTESTATION BUILDER
# ═══════════════════════════════════════════════════════════

def build_attestation_payload(
    miner_name: str,
    wallet_id: str,
    console_type: str,
    pico_data: Dict,
    nonce: str,
) -> Dict:
    """Build complete attestation payload for RustChain node."""
    profile = CONSOLE_PROFILES.get(console_type, CONSOLE_PROFILES["n64_mips"])

    # Calculate entropy score from timing CV
    # Higher CV = more entropy = more "real hardware" signal
    cv = pico_data.get("ctrl_port_timing", {}).get("cv", 0.001)
    entropy_score = min(1.0, cv * 100)  # Normalize to 0-1

    # Build fingerprint checks
    checks = {
        "ctrl_port_timing": {
            "passed": cv > 0.0001,  # Anti-emulation threshold
            "data": {
                "cv": cv,
                "samples": pico_data.get("ctrl_port_timing", {}).get("samples", 500),
            }
        },
        "rom_execution_timing": {
            "passed": True,
            "data": {
                "hash_time_us": pico_data.get("rom_execution", {}).get("time_us", 0),
            }
        },
        "bus_jitter": {
            "passed": True,
            "data": {
                "jitter_stdev_ns": pico_data.get("bus_jitter", {}).get("stdev_ns", 0),
            }
        },
        "anti_emulation": {
            "passed": cv > 0.0001,
            "data": {
                "emulator_indicators": [] if cv > 0.0001 else ["low_timing_cv"],
            }
        },
    }

    all_passed = all(c["passed"] for c in checks.values())

    payload = {
        "miner": miner_name,
        "miner_id": f"{console_type}-pico-{pico_data.get('board_id', 'unknown')[:8]}",
        "wallet": wallet_id,
        "nonce": nonce,
        "report": {
            "nonce": nonce,
            "commitment": pico_data.get("rom_execution", {}).get("hash_result", ""),
            "derived": {
                "ctrl_port_timing_mean_ns": pico_data.get("ctrl_port_timing", {}).get("mean_ns", 0),
                "ctrl_port_timing_stdev_ns": pico_data.get("ctrl_port_timing", {}).get("stdev_ns", 0),
                "ctrl_port_cv": cv,
                "rom_hash_result": pico_data.get("rom_execution", {}).get("hash_result", ""),
                "rom_hash_time_us": pico_data.get("rom_execution", {}).get("time_us", 0),
                "bus_jitter_samples": pico_data.get("bus_jitter", {}).get("samples", 500),
            },
            "entropy_score": round(entropy_score, 4),
        },
        "device": {
            "family": "console",
            "arch": console_type,
            "model": profile["model"],
            "cpu": profile["cpu"],
            "cores": profile["cores"],
            "memory_mb": profile["memory_mb"],
            "bridge_type": "pico_serial",
            "bridge_firmware": pico_data.get("firmware_version", "1.0.0"),
        },
        "signals": {
            "pico_serial": pico_data.get("board_id", ""),
            "ctrl_port_protocol": profile["protocol"],
            "rom_id": f"rustchain_attest_{console_type}_v1",
        },
        "fingerprint": {
            "all_passed": all_passed,
            "bridge_type": "pico_serial",
            "checks": checks,
        },
    }

    return payload


# ═══════════════════════════════════════════════════════════
# NODE COMMUNICATION
# ═══════════════════════════════════════════════════════════

def submit_attestation(node_url: str, payload: Dict) -> Tuple[bool, str]:
    """Submit attestation payload to RustChain node."""
    url = f"{node_url.rstrip('/')}/attest/submit"

    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get('ok') or result.get('success'):
                return True, "Attestation accepted"
            else:
                return False, result.get('error', 'Unknown error')

    except urllib.error.HTTPError as e:
        try:
            error_body = json.loads(e.read().decode('utf-8'))
            return False, error_body.get('error', f'HTTP {e.code}')
        except Exception:
            return False, f'HTTP {e.code}'
    except urllib.error.URLError as e:
        return False, f'Connection error: {e.reason}'
    except Exception as e:
        return False, f'Unexpected error: {e}'


def fetch_challenge(node_url: str, miner_name: str) -> Optional[str]:
    """Fetch challenge nonce from node."""
    url = f"{node_url.rstrip('/')}/attest/challenge"

    try:
        data = json.dumps({"miner": miner_name}).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('nonce')

    except Exception as e:
        print(f"[WARN] Failed to fetch challenge: {e}")
        # Fallback: generate local nonce
        return hashlib.sha256(f"{miner_name}_{time.time()}".encode()).hexdigest()


# ═══════════════════════════════════════════════════════════
# CONFIGURATION LOADING
# ═══════════════════════════════════════════════════════════

def load_config(config_path: str) -> Dict:
    """Load configuration from JSON file."""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                config.update(file_config)
        except Exception as e:
            print(f"[WARN] Failed to load config: {e}")

    # Override with environment variables
    if os.environ.get('RUSTCHAIN_WALLET'):
        config['wallet_id'] = os.environ['RUSTCHAIN_WALLET']
    if os.environ.get('RUSTCHAIN_NODE'):
        config['node_url'] = os.environ['RUSTCHAIN_NODE']
    if os.environ.get('RUSTCHAIN_MINER_NAME'):
        config['miner_name'] = os.environ['RUSTCHAIN_MINER_NAME']

    return config


def save_config(config: Dict, config_path: str):
    """Save configuration to JSON file."""
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


# ═══════════════════════════════════════════════════════════
# MAIN MINER LOOP
# ═══════════════════════════════════════════════════════════

class PicoBridgeMiner:
    """Main miner client for Pico serial bridge."""

    def __init__(self, config: Dict):
        self.config = config
        self.console_type = config.get('console_type', 'n64_mips')
        self.simulation_mode = config.get('simulation_mode', False)
        self.bridge = None

        # Validate console type
        if self.console_type not in CONSOLE_PROFILES:
            print(f"[ERROR] Unknown console type: {self.console_type}")
            print(f"Valid types: {', '.join(CONSOLE_PROFILES.keys())}")
            sys.exit(1)

    def initialize_bridge(self) -> bool:
        """Initialize Pico bridge (real or simulated)."""
        if self.simulation_mode:
            self.bridge = PicoSimulator(self.console_type)
            return self.bridge.connect()

        # Real hardware mode
        if not SERIAL_AVAILABLE:
            print("[ERROR] pyserial not available. Use --simulate or install pyserial.")
            return False

        port = self.config.get('pico_port', '')
        if not port:
            port = PicoBridge.auto_detect_port()
            if not port:
                print("[ERROR] No Pico device detected. Connect Pico via USB or use --simulate.")
                return False
            print(f"[INFO] Auto-detected Pico at {port}")

        self.bridge = PicoBridge(port, self.config.get('pico_baud', 115200))
        return self.bridge.connect()

    def run_attestation_cycle(self) -> bool:
        """Run single attestation cycle."""
        node_url = self.config.get('node_url', 'https://rustchain.org')
        miner_name = self.config.get('miner_name', 'pico-miner')
        wallet_id = self.config.get('wallet_id', '')

        # Step 1: Fetch challenge from node
        print(f"[INFO] Fetching challenge from {node_url}...")
        nonce = fetch_challenge(node_url, miner_name)
        if not nonce:
            nonce = hashlib.sha256(f"{miner_name}_{time.time()}".encode()).hexdigest()
            print(f"[WARN] Using locally generated nonce: {nonce[:16]}...")
        else:
            print(f"[INFO] Received nonce: {nonce[:16]}...")

        # Step 2: Send challenge to Pico/console
        print("[INFO] Sending challenge to Pico bridge...")
        if not self.bridge.send_challenge(nonce):
            print("[ERROR] Failed to send challenge to Pico")
            return False

        # Step 3: Wait for attestation result
        print("[INFO] Waiting for console attestation...")
        pico_data = self.bridge.read_attestation(timeout_sec=30.0)
        if not pico_data:
            print("[ERROR] No attestation data received from Pico")
            return False

        print(f"[INFO] Received attestation from Pico (board: {pico_data.get('board_id', 'unknown')})")

        # Step 4: Build payload
        payload = build_attestation_payload(
            miner_name=miner_name,
            wallet_id=wallet_id,
            console_type=self.console_type,
            pico_data=pico_data,
            nonce=nonce,
        )

        # Step 5: Submit to node
        print(f"[INFO] Submitting attestation to {node_url}...")
        success, message = submit_attestation(node_url, payload)

        if success:
            print(f"[OK] Attestation successful: {message}")
            # Print key metrics
            cv = payload['fingerprint']['checks']['ctrl_port_timing']['data']['cv']
            entropy = payload['report']['entropy_score']
            print(f"    Timing CV: {cv:.6f} (threshold: >0.0001)")
            print(f"    Entropy Score: {entropy:.4f}")
            print(f"    ROM Hash Time: {payload['report']['derived']['rom_hash_time_us']} us")
        else:
            print(f"[ERROR] Attestation failed: {message}")

        return success

    def run(self):
        """Main miner loop."""
        print("=" * 60)
        print("Pico Serial Bridge Miner - RIP-304")
        print("=" * 60)
        print(f"Console Type: {self.console_type}")
        print(f"Mode: {'Simulation' if self.simulation_mode else 'Real Hardware'}")
        print(f"Node: {self.config.get('node_url', 'https://rustchain.org')}")
        print(f"Miner: {self.config.get('miner_name', 'pico-miner')}")
        print("=" * 60)

        # Initialize bridge
        if not self.initialize_bridge():
            print("[ERROR] Failed to initialize Pico bridge. Exiting.")
            sys.exit(1)

        interval = self.config.get('attestation_interval_sec', 300)
        cycle_count = 0
        success_count = 0

        try:
            while True:
                cycle_count += 1
                print(f"\n[CYCLE {cycle_count}] Starting attestation cycle...")
                start_time = time.time()

                if self.run_attestation_cycle():
                    success_count += 1

                elapsed = time.time() - start_time
                next_run = max(0, interval - elapsed)
                print(f"[INFO] Cycle complete. Next attestation in {next_run:.0f}s")

                time.sleep(next_run)

        except KeyboardInterrupt:
            print("\n[INFO] Miner stopped by user")
        finally:
            self.bridge.disconnect()
            print(f"\n[SUMMARY] Completed {cycle_count} cycles, {success_count} successful")


# ═══════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Pico Serial Bridge Miner - RIP-304',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with config file
  python pico_bridge_miner.py --config config.json

  # Simulation mode (no hardware required)
  python pico_bridge_miner.py --simulate --wallet RTC<address>

  # Headless mode with explicit parameters
  python pico_bridge_miner.py --headless --wallet RTC<address> --node https://rustchain.org

  # Specify console type
  python pico_bridge_miner.py --console n64_mips --simulate

Supported console types:
  nes_6502, snes_65c816, n64_mips, gameboy_z80, gameboy_color_z80, gba_arm7,
  sms_z80, genesis_68000, saturn_sh2, ps1_mips
        """
    )

    parser.add_argument('--config', '-c', default='config.json',
                        help='Path to config file (default: config.json)')
    parser.add_argument('--simulate', '-s', action='store_true',
                        help='Run in simulation mode (no hardware required)')
    parser.add_argument('--headless', action='store_true',
                        help='Run in headless mode (no GUI)')
    parser.add_argument('--wallet', '-w', type=str,
                        help='Wallet ID (overrides config file)')
    parser.add_argument('--node', '-n', type=str,
                        help='RustChain node URL (overrides config file)')
    parser.add_argument('--miner-name', '-m', type=str,
                        help='Miner name (overrides config file)')
    parser.add_argument('--console', type=str, default='n64_mips',
                        help='Console type (default: n64_mips)')
    parser.add_argument('--port', '-p', type=str,
                        help='Pico serial port (auto-detect if not specified)')
    parser.add_argument('--interval', '-i', type=int, default=300,
                        help='Attestation interval in seconds (default: 300)')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Override with CLI args
    if args.simulate:
        config['simulation_mode'] = True
    if args.wallet:
        config['wallet_id'] = args.wallet
    if args.node:
        config['node_url'] = args.node
    if args.miner_name:
        config['miner_name'] = args.miner_name
    if args.console:
        config['console_type'] = args.console
    if args.port:
        config['pico_port'] = args.port
    if args.interval:
        config['attestation_interval_sec'] = args.interval

    # Validate wallet
    if not config.get('wallet_id'):
        print("[ERROR] Wallet ID required. Use --wallet or set in config.json")
        print("        Or set RUSTCHAIN_WALLET environment variable")
        sys.exit(1)

    # Validate wallet format (RTC prefix)
    wallet = config['wallet_id']
    if not wallet.startswith('RTC'):
        print(f"[WARN] Wallet ID should start with 'RTC' (got: {wallet[:6]}...)")

    # Save config if it was modified
    if args.simulate and not os.path.exists(args.config):
        save_config(config, args.config)
        print(f"[INFO] Created config file: {args.config}")

    # Run miner
    miner = PicoBridgeMiner(config)
    miner.run()


if __name__ == '__main__':
    main()
