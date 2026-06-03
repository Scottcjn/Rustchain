#!/usr/bin/env python3
"""
N64 Mining Host Relay — Serial Bridge to RustChain Node

Bridges the N64's serial output (via EverDrive/64drive USB)
to the RustChain attestation API.

Usage:
    python host_relay.py --port /dev/ttyUSB0 --node https://rustchain.org --wallet RTC_ADDR
    python host_relay.py --demo  # No hardware needed

Bounty: Rustchain #1877 (200 RTC)
"""

import argparse
import hashlib
import json
import struct
import sys
import time
from typing import Optional

# Protocol constants (match n64_miner.h)
ATTEST_MAGIC = 0x52544331  # "RTC1"
PKT_TYPE_ATTEST = 0
PKT_TYPE_HEARTBEAT = 1
PKT_TYPE_BALANCE = 2
PKT_TYPE_EPOCH_ACK = 3
PKT_TYPE_REATTEST = 4

CORRUPTED_SAVE_MAGIC_VALUES = {0xFFFFFFFF, 0x00000000}

FRAME_HEADER = bytes([0x52, 0x54])
DEVICE_ARCH = "mips_r4300"
DEVICE_FAMILY = "N64"


def crc8(data: bytes) -> int:
    """CRC-8/MAXIM — matches the N64 ROM implementation."""
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


class N64Relay:
    """Bridges N64 serial ↔ RustChain API."""

    def __init__(self, port: Optional[str], node_url: str, wallet: str, demo: bool = False):
        self.node_url = node_url.rstrip("/")
        self.wallet = wallet
        self.demo = demo
        self.serial_conn = None
        self.attestations_sent = 0
        self.attestations_ok = 0
        self.corrupt_attestations = 0
        self.health_events = []
        self.total_earned = 0
        self.current_epoch = 0

        if not demo and port:
            try:
                import serial
                self.serial_conn = serial.Serial(port, 115200, timeout=5)
                print(f"[relay] Connected to N64 via {port}")
            except ImportError:
                print("[relay] pyserial not installed. pip install pyserial")
                sys.exit(1)
            except Exception as e:
                print(f"[relay] Serial error: {e}")
                sys.exit(1)

    def recv_frame(self) -> Optional[bytes]:
        """Read a framed packet from N64."""
        if self.demo:
            return self._demo_attestation()

        if not self.serial_conn:
            return None

        # Sync to frame header
        buf = self.serial_conn.read(2)
        if buf != FRAME_HEADER:
            return None

        len_bytes = self.serial_conn.read(2)
        if len(len_bytes) < 2:
            return None

        payload_len = struct.unpack(">H", len_bytes)[0]
        payload = self.serial_conn.read(payload_len)
        checksum = self.serial_conn.read(1)

        if len(payload) < payload_len or len(checksum) < 1:
            return None

        if crc8(payload) != checksum[0]:
            print("[relay] CRC mismatch — dropped frame")
            return None

        return payload

    def send_frame(self, data: bytes) -> bool:
        """Send a framed response to N64."""
        if self.demo:
            return True

        if not self.serial_conn:
            return False

        header = FRAME_HEADER + struct.pack(">H", len(data))
        checksum = bytes([crc8(data)])
        self.serial_conn.write(header + data + checksum)
        return True

    def emit_health_event(self, event: dict) -> None:
        """Record a miner health event for node-side observers."""
        self.health_events.append(event)

    def send_reattest_request(self, epoch: int) -> bool:
        """Ask the miner to re-attest from the last known checkpoint."""
        req = struct.pack("<IBBHI",
                          ATTEST_MAGIC,
                          1,  # version
                          PKT_TYPE_REATTEST,
                          0,  # payload_len
                          epoch)
        return self.send_frame(req)

    def _record_corrupt_attestation(self, magic: int) -> None:
        """Log and surface corrupted cartridge save-data markers."""
        self.corrupt_attestations += 1
        event = {
            "type": "miner_attestation_corrupt",
            "severity": "warn",
            "magic": f"0x{magic:08X}",
            "block_height": self.current_epoch,
            "epoch": self.current_epoch,
            "action": "reattest_requested",
        }
        print(
            "[relay][WARN] miner_attestation_corrupt: "
            f"magic=0x{magic:08X} block_height={self.current_epoch}; "
            "requesting re-attest"
        )
        self.emit_health_event(event)
        self.send_reattest_request(self.current_epoch)

    def _demo_attestation(self) -> bytes:
        """Generate a fake attestation packet for demo mode."""
        import os
        time.sleep(2)  # Simulate real timing

        # Build attestation_packet_t structure
        header = struct.pack("<IBBh",
                             ATTEST_MAGIC,  # magic
                             1,  # version
                             PKT_TYPE_ATTEST,  # type
                             0)  # payload_len (unused in relay)

        device_arch = DEVICE_ARCH.encode().ljust(16, b'\x00')
        device_family = DEVICE_FAMILY.encode().ljust(8, b'\x00')
        miner_id = self.wallet[:31].encode().ljust(32, b'\x00')
        epoch = struct.pack("<I", self.current_epoch)

        # Simulated fingerprint measurements (realistic N64 values)
        fp = struct.pack("<IIIIIII",
                         213,   # count_drift_ns (typical: 50-500)
                         2,     # cache_d_hit_cycles
                         42,    # cache_d_miss_cycles
                         1,     # cache_i_hit_cycles
                         38,    # cache_i_miss_cycles
                         47,    # rsp_jitter_ns
                         31)    # tlb_miss_cycles

        fp_hash = hashlib.sha256(fp).digest()

        return header + device_arch + device_family + miner_id + epoch + fp + fp_hash

    def parse_attestation(self, data: bytes) -> Optional[dict]:
        """Parse an attestation packet from N64."""
        if len(data) < 8:
            return None

        magic = struct.unpack_from("<I", data, 0)[0]
        if magic in CORRUPTED_SAVE_MAGIC_VALUES:
            self._record_corrupt_attestation(magic)
            return None

        if magic != ATTEST_MAGIC:
            return None

        pkt_type = data[5]
        if pkt_type != PKT_TYPE_ATTEST:
            return None

        offset = 8  # After header
        device_arch = data[offset:offset + 16].rstrip(b'\x00').decode('ascii', errors='replace')
        offset += 16
        device_family = data[offset:offset + 8].rstrip(b'\x00').decode('ascii', errors='replace')
        offset += 8
        miner_id = data[offset:offset + 32].rstrip(b'\x00').decode('ascii', errors='replace')
        offset += 32
        epoch = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        # Fingerprint
        if len(data) >= offset + 28:
            fp_vals = struct.unpack_from("<IIIIIII", data, offset)
            offset += 28
            fp_hash = data[offset:offset + 32].hex() if len(data) >= offset + 32 else ""
        else:
            fp_vals = (0,) * 7
            fp_hash = ""

        return {
            "device_arch": device_arch,
            "device_family": device_family,
            "miner_id": miner_id,
            "epoch": epoch,
            "fingerprint_hash": fp_hash,
            "measurements": {
                "count_drift_ns": fp_vals[0],
                "cache_d_hit_cycles": fp_vals[1],
                "cache_d_miss_cycles": fp_vals[2],
                "cache_i_hit_cycles": fp_vals[3],
                "cache_i_miss_cycles": fp_vals[4],
                "rsp_jitter_ns": fp_vals[5],
                "tlb_miss_cycles": fp_vals[6],
            }
        }

    def submit_attestation(self, attest: dict) -> Optional[dict]:
        """Submit attestation to RustChain node."""
        try:
            import urllib.request
            payload = json.dumps(attest).encode()
            req = urllib.request.Request(
                f"{self.node_url}/attest/submit",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read())
        except Exception as e:
            print(f"[relay] Attestation submit failed: {e}")
            return None

    def send_epoch_ack(self, epoch: int, balance: int, multiplier: float) -> bool:
        """Send epoch acknowledgment back to N64."""
        ack = struct.pack("<IBBHI Qi",
                          ATTEST_MAGIC,
                          1,  # version
                          PKT_TYPE_EPOCH_ACK,
                          0,  # payload_len
                          epoch,
                          balance,
                          int(multiplier * 100))
        return self.send_frame(ack)

    def run(self):
        """Main relay loop."""
        print(f"[relay] N64 Mining Relay {'(DEMO)' if self.demo else ''}")
        print(f"[relay] Node: {self.node_url}")
        print(f"[relay] Wallet: {self.wallet}")
        print(f"[relay] Waiting for N64 attestation packets...")

        while True:
            try:
                frame = self.recv_frame()
                if frame is None:
                    continue

                attest = self.parse_attestation(frame)
                if attest is None:
                    print("[relay] Invalid packet — skipping")
                    continue

                self.attestations_sent += 1
                print(f"\n[relay] Attestation #{self.attestations_sent}")
                print(f"  Device: {attest['device_arch']} ({attest['device_family']})")
                print(f"  Epoch: {attest['epoch']}")
                print(f"  Drift: {attest['measurements']['count_drift_ns']}ns")
                print(f"  Cache hit/miss: {attest['measurements']['cache_d_hit_cycles']}/{attest['measurements']['cache_d_miss_cycles']} cycles")
                print(f"  RSP jitter: {attest['measurements']['rsp_jitter_ns']}ns")
                print(f"  TLB miss: {attest['measurements']['tlb_miss_cycles']} cycles")

                # Submit to node
                result = self.submit_attestation(attest)
                if result and result.get("ok"):
                    self.attestations_ok += 1
                    earned = result.get("reward", 0)
                    self.total_earned += earned
                    self.current_epoch = result.get("epoch", self.current_epoch + 1)
                    multiplier = result.get("multiplier", 4.0)
                    print(f"  ✅ Accepted! Earned: {earned} nRTC (4.0x MYTHIC)")
                    self.send_epoch_ack(self.current_epoch, self.total_earned, multiplier)
                else:
                    print(f"  ❌ Rejected: {result}")
                    # Still increment epoch for demo
                    if self.demo:
                        self.current_epoch += 1
                        self.attestations_ok += 1
                        print(f"  [demo] Simulating acceptance — epoch {self.current_epoch}")

                print(f"  Stats: {self.attestations_ok}/{self.attestations_sent} accepted, {self.total_earned} nRTC total")

            except KeyboardInterrupt:
                print("\n[relay] Shutting down...")
                break
            except Exception as e:
                print(f"[relay] Error: {e}")
                time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description="N64 Mining Host Relay")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="Serial port")
    parser.add_argument("--node", default="https://rustchain.org", help="RustChain node URL")
    parser.add_argument("--wallet", default="n64-miner-001", help="RTC wallet address")
    parser.add_argument("--demo", action="store_true", help="Run without hardware")
    args = parser.parse_args()

    relay = N64Relay(
        port=args.port if not args.demo else None,
        node_url=args.node,
        wallet=args.wallet,
        demo=args.demo
    )
    relay.run()


if __name__ == "__main__":
    main()
