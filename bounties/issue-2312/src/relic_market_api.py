#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Rent-a-Relic Market API
Issue #2312: Book authenticated vintage compute

A WebRTC-powered reservation system for AI agents to book authenticated
time on named vintage machines through MCP and Beacon, with provenance receipts.
"""

import os
import json
import time
import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
import logging

from flask import Flask, jsonify, request, Response
import nacl.signing
import nacl.encoding

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('relic_market')


class AccessDuration(Enum):
    """Available rental duration options"""
    ONE_HOUR = 1
    FOUR_HOURS = 4
    TWENTY_FOUR_HOURS = 24


class ReservationStatus(Enum):
    """Reservation lifecycle states"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class VintageMachine:
    """Represents a vintage compute machine available for rent"""
    machine_id: str
    name: str
    architecture: str
    cpu_model: str
    cpu_speed_ghz: float
    ram_gb: int
    storage_gb: int
    gpu_model: Optional[str]
    os: str
    year: int
    manufacturer: str
    description: str
    photo_urls: List[str]
    ssh_port: int
    api_port: int
    uptime_hours: int = 0
    total_reservations: int = 0
    attestation_history: List[Dict] = field(default_factory=list)
    passport_id: Optional[str] = None
    ed25519_public_key: Optional[str] = None
    is_available: bool = True
    hourly_rate_rtc: float = 10.0
    location: str = "RustChain Data Center"
    capabilities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Reservation:
    """Represents a machine reservation"""
    reservation_id: str
    machine_id: str
    agent_id: str
    start_time: float
    end_time: float
    duration_hours: int
    total_cost_rtc: float
    status: str
    escrow_tx_hash: str
    ssh_credentials: Optional[Dict] = None
    api_key: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    access_granted_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ProvenanceReceipt:
    """Cryptographically signed proof of compute session"""
    receipt_id: str
    session_id: str
    machine_passport_id: str
    machine_id: str
    agent_id: str
    session_start: float
    session_end: float
    duration_seconds: int
    compute_hash: str
    hardware_attestation: Dict
    signature: str
    signed_at: float
    signature_algorithm: str = "Ed25519"
    
    def to_dict(self) -> Dict:
        return asdict(self)


class MachineRegistry:
    """Registry of available vintage machines"""
    
    def __init__(self):
        self.machines: Dict[str, VintageMachine] = {}
        self._lock = threading.RLock()
        self._initialize_sample_machines()
    
    def _initialize_sample_machines(self):
        """Initialize with sample vintage machines"""
        sample_machines = [
            VintageMachine(
                machine_id="vm-001",
                name="POWER8 Beast",
                architecture="ppc64",
                cpu_model="IBM POWER8",
                cpu_speed_ghz=4.0,
                ram_gb=512,
                storage_gb=2000,
                gpu_model="NVIDIA Tesla K80",
                os="Ubuntu 20.04 PPC64",
                year=2013,
                manufacturer="IBM",
                description="High-memory POWER8 system perfect for large language model inference",
                photo_urls=["/static/machines/power8-front.jpg", "/static/machines/power8-rack.jpg"],
                ssh_port=22001,
                api_port=50001,
                uptime_hours=8760,
                passport_id="passport-power8-001",
                hourly_rate_rtc=50.0,
                capabilities=["llm-inference", "batch-processing", "video-rendering"],
                attestation_history=[
                    {"date": "2026-03-20", "type": "hardware", "verified": True, "hash": "a1b2c3d4"}
                ]
            ),
            VintageMachine(
                machine_id="vm-002",
                name="G5 Tower",
                architecture="ppc64",
                cpu_model="PowerPC G5",
                cpu_speed_ghz=2.5,
                ram_gb=16,
                storage_gb=500,
                gpu_model="ATI Radeon X800",
                os="Mac OS X 10.5 Leopard",
                year=2005,
                manufacturer="Apple",
                description="Classic PowerMac G5 for authentic vintage Mac compute",
                photo_urls=["/static/machines/g5-tower.jpg"],
                ssh_port=22002,
                api_port=50002,
                uptime_hours=4380,
                passport_id="passport-g5-002",
                hourly_rate_rtc=15.0,
                capabilities=["video-rendering", "audio-processing", "legacy-mac-testing"],
                attestation_history=[
                    {"date": "2026-03-19", "type": "hardware", "verified": True, "hash": "e5f6g7h8"}
                ]
            ),
            VintageMachine(
                machine_id="vm-003",
                name="Pentium III Workstation",
                architecture="x86",
                cpu_model="Intel Pentium III",
                cpu_speed_ghz=1.0,
                ram_gb=2,
                storage_gb=80,
                gpu_model="NVIDIA GeForce 2 MX",
                os="Windows 2000",
                year=2000,
                manufacturer="Dell",
                description="Authentic Y2K-era workstation for retro computing",
                photo_urls=["/static/machines/p3-workstation.jpg"],
                ssh_port=22003,
                api_port=50003,
                uptime_hours=2190,
                passport_id="passport-p3-003",
                hourly_rate_rtc=8.0,
                capabilities=["retro-gaming", "legacy-windows-testing", "benchmarking"],
                attestation_history=[
                    {"date": "2026-03-18", "type": "hardware", "verified": True, "hash": "i9j0k1l2"}
                ]
            ),
            VintageMachine(
                machine_id="vm-004",
                name="SPARCstation 20",
                architecture="sparc",
                cpu_model="SuperSPARC",
                cpu_speed_ghz=0.075,
                ram_gb=0.256,
                storage_gb=4,
                gpu_model="Creator3D",
                os="Solaris 2.5",
                year=1995,
                manufacturer="Sun Microsystems",
                description="Classic Unix workstation from the golden age",
                photo_urls=["/static/machines/sparc20.jpg"],
                ssh_port=22004,
                api_port=50004,
                uptime_hours=1095,
                passport_id="passport-sparc-004",
                hourly_rate_rtc=12.0,
                capabilities=["unix-history", "legacy-solaris-testing", "educational"],
                attestation_history=[
                    {"date": "2026-03-17", "type": "hardware", "verified": True, "hash": "m3n4o5p6"}
                ]
            ),
            VintageMachine(
                machine_id="vm-005",
                name="AlphaServer 800",
                architecture="alpha",
                cpu_model="DEC Alpha 21164",
                cpu_speed_ghz=0.6,
                ram_gb=4,
                storage_gb=100,
                gpu_model="PGX",
                os="Tru64 UNIX",
                year=1996,
                manufacturer="Digital Equipment Corporation",
                description="64-bit Alpha architecture for unique compute workloads",
                photo_urls=["/static/machines/alpha800.jpg"],
                ssh_port=22005,
                api_port=50005,
                uptime_hours=3285,
                passport_id="passport-alpha-005",
                hourly_rate_rtc=20.0,
                capabilities=["64bit-compute", "legacy-unix", "scientific"],
                attestation_history=[
                    {"date": "2026-03-21", "type": "hardware", "verified": True, "hash": "q7r8s9t0"}
                ]
            ),
        ]
        
        for machine in sample_machines:
            self.machines[machine.machine_id] = machine
    
    def list_machines(self, available_only: bool = False) -> List[VintageMachine]:
        """List all registered machines"""
        with self._lock:
            if available_only:
                return [m for m in self.machines.values() if m.is_available]
            return list(self.machines.values())
    
    def get_machine(self, machine_id: str) -> Optional[VintageMachine]:
        """Get a specific machine by ID"""
        with self._lock:
            return self.machines.get(machine_id)
    
    def update_uptime(self, machine_id: str, hours: int):
        """Update machine uptime"""
        with self._lock:
            if machine_id in self.machines:
                self.machines[machine_id].uptime_hours += hours
    
    def increment_reservations(self, machine_id: str):
        """Increment total reservation count"""
        with self._lock:
            if machine_id in self.machines:
                self.machines[machine_id].total_reservations += 1
    
    def add_attestation(self, machine_id: str, attestation: Dict):
        """Add attestation to machine history"""
        with self._lock:
            if machine_id in self.machines:
                self.machines[machine_id].attestation_history.append(attestation)
    
    def set_availability(self, machine_id: str, available: bool):
        """Set machine availability status"""
        with self._lock:
            if machine_id in self.machines:
                self.machines[machine_id].is_available = available


class EscrowManager:
    """Manages RTC escrow for reservations"""
    
    def __init__(self):
        self.escrows: Dict[str, Dict] = {}
        self._lock = threading.RLock()
    
    def lock_funds(self, reservation_id: str, agent_id: str, amount_rtc: float) -> str:
        """Lock funds in escrow, returns transaction hash"""
        with self._lock:
            tx_hash = hashlib.sha256(
                f"{reservation_id}:{agent_id}:{amount_rtc}:{time.time()}".encode()
            ).hexdigest()
            
            self.escrows[reservation_id] = {
                "tx_hash": tx_hash,
                "agent_id": agent_id,
                "amount_rtc": amount_rtc,
                "locked_at": time.time(),
                "status": "locked",
                "released": False
            }
            
            logger.info(f"Escrow locked: {tx_hash[:16]}... for {amount_rtc} RTC")
            return tx_hash
    
    def release_funds(self, reservation_id: str, recipient: str) -> bool:
        """Release escrow funds to recipient"""
        with self._lock:
            if reservation_id not in self.escrows:
                return False
            
            escrow = self.escrows[reservation_id]
            if escrow["released"]:
                return False
            
            escrow["released"] = True
            escrow["released_to"] = recipient
            escrow["released_at"] = time.time()
            escrow["status"] = "released"
            
            logger.info(f"Escrow released: {escrow['tx_hash'][:16]}... to {recipient}")
            return True
    
    def refund(self, reservation_id: str) -> bool:
        """Refund escrow to agent"""
        with self._lock:
            if reservation_id not in self.escrows:
                return False
            
            escrow = self.escrows[reservation_id]
            if escrow["released"]:
                return False
            
            escrow["refunded"] = True
            escrow["refunded_at"] = time.time()
            escrow["status"] = "refunded"
            
            logger.info(f"Escrow refunded: {escrow['tx_hash'][:16]}...")
            return True
    
    def get_escrow(self, reservation_id: str) -> Optional[Dict]:
        """Get escrow details"""
        with self._lock:
            return self.escrows.get(reservation_id)


class ReceiptSigner:
    """Signs provenance receipts with machine Ed25519 keys"""
    
    def __init__(self):
        self.machine_keys: Dict[str, nacl.signing.SigningKey] = {}
        self._initialize_machine_keys()
    
    def _initialize_machine_keys(self):
        """Initialize Ed25519 keys for machines"""
        # In production, these would be securely stored per machine
        # For demo, we generate deterministic keys from machine IDs
        sample_keys = [
            ("vm-001", "power8-beast-key-seed-001"),
            ("vm-002", "g5-tower-key-seed-002"),
            ("vm-003", "p3-workstation-key-seed-003"),
            ("vm-004", "sparcstation-20-key-seed-004"),
            ("vm-005", "alphaserver-800-key-seed-005"),
        ]
        
        for machine_id, seed in sample_keys:
            seed_hash = hashlib.sha256(seed.encode()).digest()[:32]
            self.machine_keys[machine_id] = nacl.signing.SigningKey(seed_hash)
    
    def get_public_key(self, machine_id: str) -> Optional[str]:
        """Get machine's public key as hex string"""
        if machine_id not in self.machine_keys:
            return None
        
        signing_key = self.machine_keys[machine_id]
        return signing_key.verify_key.encode().hex()
    
    def sign_receipt(self, receipt_data: Dict, machine_id: str) -> Optional[str]:
        """Sign receipt data with machine's private key"""
        if machine_id not in self.machine_keys:
            return None

        signing_key = self.machine_keys[machine_id]

        # Canonical JSON for signing
        canonical = json.dumps(receipt_data, sort_keys=True, separators=(',', ':'))
        message = canonical.encode('utf-8')

        # Sign - use sign() which returns SignedMessage, extract only the signature
        signed = signing_key.sign(message)
        return bytes(signed.signature).hex()
    
    def verify_signature(self, data: Dict, signature: str, machine_id: str) -> bool:
        """Verify a signature using machine's public key"""
        if machine_id not in self.machine_keys:
            return False

        try:
            signing_key = self.machine_keys[machine_id]
            verify_key = signing_key.verify_key

            canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
            message = canonical.encode('utf-8')

            # Decode signature from hex and verify
            signature_bytes = bytes.fromhex(signature)
            verify_key.verify(message, signature=signature_bytes)
            return True
        except Exception:
            return False


class ReservationManager:
    """Manages reservation lifecycle"""
    
    def __init__(self, registry: MachineRegistry, escrow: EscrowManager, signer: ReceiptSigner):
        self.registry = registry
        self.escrow = escrow
        self.signer = signer
        self.reservations: Dict[str, Reservation] = {}
        self.receipts: Dict[str, ProvenanceReceipt] = {}
        self._lock = threading.RLock()
    
    def create_reservation(
        self,
        machine_id: str,
        agent_id: str,
        duration_hours: int,
        payment_rtc: float
    ) -> Tuple[Optional[Reservation], Optional[str]]:
        """Create a new reservation"""
        with self._lock:
            machine = self.registry.get_machine(machine_id)
            if not machine:
                return None, "Machine not found"
            
            if not machine.is_available:
                return None, "Machine not available"
            
            # Validate duration
            valid_durations = [d.value for d in AccessDuration]
            if duration_hours not in valid_durations:
                return None, f"Invalid duration. Must be one of: {valid_durations}"
            
            # Calculate cost
            total_cost = machine.hourly_rate_rtc * duration_hours
            if payment_rtc < total_cost:
                return None, f"Insufficient payment. Required: {total_cost} RTC"
            
            # Generate reservation
            reservation_id = f"res-{secrets.token_hex(8)}"
            start_time = time.time()
            end_time = start_time + (duration_hours * 3600)
            
            # Lock escrow
            escrow_tx = self.escrow.lock_funds(reservation_id, agent_id, total_cost)
            
            # Generate access credentials
            ssh_password = secrets.token_urlsafe(16)
            api_key = secrets.token_urlsafe(32)
            
            reservation = Reservation(
                reservation_id=reservation_id,
                machine_id=machine_id,
                agent_id=agent_id,
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                total_cost_rtc=total_cost,
                status=ReservationStatus.CONFIRMED.value,
                escrow_tx_hash=escrow_tx,
                ssh_credentials={
                    "username": f"agent-{agent_id[:8]}",
                    "password": ssh_password,
                    "port": machine.ssh_port,
                    "host": f"{machine_id}.relic.rustchain.org"
                },
                api_key=api_key
            )
            
            self.reservations[reservation_id] = reservation
            self.registry.increment_reservations(machine_id)
            
            logger.info(f"Reservation created: {reservation_id} for {machine_id}")
            return reservation, None
    
    def start_session(self, reservation_id: str) -> Optional[str]:
        """Mark reservation as active"""
        with self._lock:
            if reservation_id not in self.reservations:
                return "Reservation not found"
            
            reservation = self.reservations[reservation_id]
            if reservation.status != ReservationStatus.CONFIRMED.value:
                return f"Invalid status: {reservation.status}"
            
            reservation.status = ReservationStatus.ACTIVE.value
            reservation.access_granted_at = time.time()
            
            logger.info(f"Session started: {reservation_id}")
            return None
    
    def complete_session(
        self,
        reservation_id: str,
        compute_hash: str,
        hardware_attestation: Dict
    ) -> Tuple[Optional[ProvenanceReceipt], Optional[str]]:
        """Complete session and generate provenance receipt"""
        with self._lock:
            if reservation_id not in self.reservations:
                return None, "Reservation not found"
            
            reservation = self.reservations[reservation_id]
            if reservation.status != ReservationStatus.ACTIVE.value:
                return None, f"Invalid status: {reservation.status}"
            
            # Update reservation
            reservation.status = ReservationStatus.COMPLETED.value
            reservation.completed_at = time.time()
            
            # Release escrow to machine operator
            self.escrow.release_funds(reservation_id, f"operator-{reservation.machine_id}")
            
            # Generate receipt
            machine = self.registry.get_machine(reservation.machine_id)
            if not machine or not machine.passport_id:
                return None, "Machine passport not found"
            
            receipt_id = f"receipt-{secrets.token_hex(8)}"
            session_duration = int(reservation.completed_at - reservation.access_granted_at)
            
            # Prepare receipt data for signing
            receipt_data = {
                "receipt_id": receipt_id,
                "session_id": reservation_id,
                "machine_passport_id": machine.passport_id,
                "machine_id": reservation.machine_id,
                "agent_id": reservation.agent_id,
                "session_start": reservation.access_granted_at,
                "session_end": reservation.completed_at,
                "duration_seconds": session_duration,
                "compute_hash": compute_hash,
                "hardware_attestation": hardware_attestation,
                "signed_at": time.time(),
                "signature_algorithm": "Ed25519"
            }
            
            # Sign with machine key
            signature = self.signer.sign_receipt(receipt_data, reservation.machine_id)
            if not signature:
                return None, "Failed to sign receipt"
            
            receipt = ProvenanceReceipt(
                receipt_id=receipt_id,
                session_id=reservation_id,
                machine_passport_id=machine.passport_id,
                machine_id=reservation.machine_id,
                agent_id=reservation.agent_id,
                session_start=reservation.access_granted_at,
                session_end=reservation.completed_at,
                duration_seconds=session_duration,
                compute_hash=compute_hash,
                hardware_attestation=hardware_attestation,
                signature=signature,
                signed_at=time.time()
            )
            
            self.receipts[receipt_id] = receipt
            
            # Add attestation to machine history
            self.registry.add_attestation(reservation.machine_id, {
                "date": datetime.now().isoformat(),
                "type": "session_completion",
                "verified": True,
                "hash": compute_hash[:16],
                "session_id": reservation_id
            })
            
            logger.info(f"Session completed with receipt: {receipt_id}")
            return receipt, None
    
    def get_reservation(self, reservation_id: str) -> Optional[Reservation]:
        """Get reservation by ID"""
        with self._lock:
            return self.reservations.get(reservation_id)
    
    def get_receipt(self, session_id: str) -> Optional[ProvenanceReceipt]:
        """Get receipt by session ID"""
        with self._lock:
            for receipt in self.receipts.values():
                if receipt.session_id == session_id:
                    return receipt
            return None
    
    def get_agent_reservations(self, agent_id: str) -> List[Reservation]:
        """Get all reservations for an agent"""
        with self._lock:
            return [r for r in self.reservations.values() if r.agent_id == agent_id]
    
    def get_most_rented_machines(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get leaderboard of most rented machines"""
        with self._lock:
            machines = [(m.machine_id, m.total_reservations) for m in self.registry.list_machines()]
            machines.sort(key=lambda x: x[1], reverse=True)
            return machines[:limit]


class MCPIntegration:
    """Model Context Protocol integration for AI agents"""
    
    def __init__(self, reservation_manager: ReservationManager):
        self.reservation_manager = reservation_manager
        self.tools = self._register_tools()
    
    def _register_tools(self) -> Dict:
        """Register MCP tools"""
        return {
            "list_machines": {
                "description": "List available vintage machines for rent",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "available_only": {
                            "type": "boolean",
                            "description": "Only show available machines"
                        }
                    }
                }
            },
            "reserve_machine": {
                "description": "Reserve a vintage machine for compute session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {"type": "string", "description": "Machine ID to reserve"},
                        "duration_hours": {"type": "integer", "enum": [1, 4, 24], "description": "Session duration"},
                        "agent_id": {"type": "string", "description": "Agent identifier"},
                        "payment_rtc": {"type": "number", "description": "Payment amount in RTC"}
                    },
                    "required": ["machine_id", "duration_hours", "agent_id", "payment_rtc"]
                }
            },
            "get_reservation": {
                "description": "Get reservation details",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reservation_id": {"type": "string", "description": "Reservation ID"}
                    },
                    "required": ["reservation_id"]
                }
            },
            "get_receipt": {
                "description": "Get provenance receipt for completed session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session/reservation ID"}
                    },
                    "required": ["session_id"]
                }
            },
            "start_session": {
                "description": "Start a reserved compute session",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reservation_id": {"type": "string", "description": "Reservation ID"}
                    },
                    "required": ["reservation_id"]
                }
            },
            "complete_session": {
                "description": "Complete session and get provenance receipt",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "reservation_id": {"type": "string", "description": "Reservation ID"},
                        "compute_hash": {"type": "string", "description": "SHA256 hash of compute output"},
                        "hardware_attestation": {"type": "object", "description": "Hardware attestation proof"}
                    },
                    "required": ["reservation_id", "compute_hash", "hardware_attestation"]
                }
            }
        }
    
    def handle_tool_call(self, tool_name: str, arguments: Dict) -> Dict:
        """Handle MCP tool call"""
        if tool_name == "list_machines":
            available_only = arguments.get("available_only", True)
            machines = [m.to_dict() for m in self.reservation_manager.registry.list_machines(available_only)]
            return {"machines": machines, "count": len(machines)}
        
        elif tool_name == "reserve_machine":
            reservation, error = self.reservation_manager.create_reservation(
                machine_id=arguments["machine_id"],
                agent_id=arguments["agent_id"],
                duration_hours=arguments["duration_hours"],
                payment_rtc=arguments["payment_rtc"]
            )
            if error:
                return {"error": error}
            return {"reservation": reservation.to_dict()}
        
        elif tool_name == "get_reservation":
            reservation = self.reservation_manager.get_reservation(arguments["reservation_id"])
            if not reservation:
                return {"error": "Reservation not found"}
            return {"reservation": reservation.to_dict()}
        
        elif tool_name == "get_receipt":
            receipt = self.reservation_manager.get_receipt(arguments["session_id"])
            if not receipt:
                return {"error": "Receipt not found"}
            return {"receipt": receipt.to_dict()}
        
        elif tool_name == "start_session":
            error = self.reservation_manager.start_session(arguments["reservation_id"])
            if error:
                return {"error": error}
            return {"status": "session_started"}
        
        elif tool_name == "complete_session":
            receipt, error = self.reservation_manager.complete_session(
                reservation_id=arguments["reservation_id"],
                compute_hash=arguments["compute_hash"],
                hardware_attestation=arguments["hardware_attestation"]
            )
            if error:
                return {"error": error}
            return {"receipt": receipt.to_dict()}
        
        return {"error": f"Unknown tool: {tool_name}"}
    
    def get_mcp_manifest(self) -> Dict:
        """Get MCP server manifest"""
        return {
            "mcpVersion": "1.0.0",
            "name": "rustchain-relic-market",
            "version": "1.0.0",
            "description": "Rent-a-Relic Market - Book authenticated vintage compute",
            "tools": self.tools
        }


class BeaconIntegration:
    """Beacon message protocol integration"""
    
    def __init__(self, reservation_manager: ReservationManager):
        self.reservation_manager = reservation_manager
        self.message_handlers = self._register_handlers()
    
    def _register_handlers(self) -> Dict:
        """Register Beacon message handlers"""
        return {
            "RESERVE": self._handle_reserve,
            "CANCEL": self._handle_cancel,
            "START": self._handle_start,
            "COMPLETE": self._handle_complete,
            "STATUS": self._handle_status,
            "RECEIPT": self._handle_receipt_request
        }
    
    def _handle_reserve(self, payload: Dict) -> Dict:
        """Handle reservation request via Beacon"""
        required = ["machine_id", "agent_id", "duration_hours", "payment_rtc"]
        if not all(k in payload for k in required):
            return {"error": "Missing required fields", "required": required}
        
        reservation, error = self.reservation_manager.create_reservation(
            machine_id=payload["machine_id"],
            agent_id=payload["agent_id"],
            duration_hours=payload["duration_hours"],
            payment_rtc=payload["payment_rtc"]
        )
        
        if error:
            return {"status": "error", "message": error}
        
        return {
            "status": "confirmed",
            "reservation_id": reservation.reservation_id,
            "machine_id": reservation.machine_id,
            "duration_hours": reservation.duration_hours,
            "total_cost_rtc": reservation.total_cost_rtc,
            "escrow_tx": reservation.escrow_tx_hash[:16] + "..."
        }
    
    def _handle_cancel(self, payload: Dict) -> Dict:
        """Handle cancellation request"""
        reservation_id = payload.get("reservation_id")
        if not reservation_id:
            return {"error": "Missing reservation_id"}
        
        reservation = self.reservation_manager.get_reservation(reservation_id)
        if not reservation:
            return {"status": "error", "message": "Reservation not found"}
        
        # Refund escrow
        self.reservation_manager.escrow.refund(reservation_id)
        reservation.status = ReservationStatus.CANCELLED.value
        
        return {"status": "cancelled", "refund_status": "processed"}
    
    def _handle_start(self, payload: Dict) -> Dict:
        """Handle session start request"""
        reservation_id = payload.get("reservation_id")
        if not reservation_id:
            return {"error": "Missing reservation_id"}
        
        error = self.reservation_manager.start_session(reservation_id)
        if error:
            return {"status": "error", "message": error}
        
        reservation = self.reservation_manager.get_reservation(reservation_id)
        return {
            "status": "active",
            "ssh": reservation.ssh_credentials,
            "api_key": reservation.api_key,
            "expires_at": reservation.end_time
        }
    
    def _handle_complete(self, payload: Dict) -> Dict:
        """Handle session completion"""
        required = ["reservation_id", "compute_hash", "hardware_attestation"]
        if not all(k in payload for k in required):
            return {"error": "Missing required fields", "required": required}
        
        receipt, error = self.reservation_manager.complete_session(
            reservation_id=payload["reservation_id"],
            compute_hash=payload["compute_hash"],
            hardware_attestation=payload["hardware_attestation"]
        )
        
        if error:
            return {"status": "error", "message": error}
        
        return {
            "status": "completed",
            "receipt_id": receipt.receipt_id,
            "signature": receipt.signature[:32] + "..."
        }
    
    def _handle_status(self, payload: Dict) -> Dict:
        """Handle status query"""
        reservation_id = payload.get("reservation_id")
        if not reservation_id:
            return {"error": "Missing reservation_id"}
        
        reservation = self.reservation_manager.get_reservation(reservation_id)
        if not reservation:
            return {"status": "error", "message": "Reservation not found"}
        
        return {"reservation": reservation.to_dict()}
    
    def _handle_receipt_request(self, payload: Dict) -> Dict:
        """Handle receipt query"""
        session_id = payload.get("session_id")
        if not session_id:
            return {"error": "Missing session_id"}
        
        receipt = self.reservation_manager.get_receipt(session_id)
        if not receipt:
            return {"status": "error", "message": "Receipt not found"}
        
        return {"receipt": receipt.to_dict()}
    
    def handle_message(self, message_type: str, payload: Dict) -> Dict:
        """Handle incoming Beacon message"""
        handler = self.message_handlers.get(message_type)
        if not handler:
            return {"error": f"Unknown message type: {message_type}"}
        
        try:
            return handler(payload)
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Flask Application
app = Flask(__name__)

# Initialize components
registry = MachineRegistry()
escrow = EscrowManager()
signer = ReceiptSigner()
reservation_manager = ReservationManager(registry, escrow, signer)
mcp = MCPIntegration(reservation_manager)
beacon = BeaconIntegration(reservation_manager)


def _json_object_body():
    data = request.get_json(silent=True)
    if data is None:
        if request.get_data(cache=True):
            return None, (jsonify({"error": "JSON object required"}), 400)
        return None, (jsonify({"error": "Request body required"}), 400)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "JSON object required"}), 400)
    return data, None


def _positive_limit(default: int = 10):
    raw = request.args.get('limit', str(default))
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit must be an integer"}), 400)
    if limit < 1:
        return None, (jsonify({"error": "limit must be positive"}), 400)
    return limit, None


# ============== API Endpoints ==============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "ok": True,
        "service": "relic-market",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "machines_registered": len(registry.list_machines()),
        "active_reservations": len([r for r in reservation_manager.reservations.values() 
                                   if r.status == ReservationStatus.ACTIVE.value])
    })


@app.route('/relic/available', methods=['GET'])
def get_available_machines():
    """GET /relic/available - List available machines"""
    available_only = request.args.get('available_only', 'true').lower() == 'true'
    machines = registry.list_machines(available_only=available_only)
    
    return jsonify({
        "machines": [m.to_dict() for m in machines],
        "count": len(machines),
        "timestamp": datetime.now().isoformat()
    })


@app.route('/relic/<machine_id>', methods=['GET'])
def get_machine_details(machine_id: str):
    """Get detailed machine information"""
    machine = registry.get_machine(machine_id)
    if not machine:
        return jsonify({"error": "Machine not found"}), 404
    
    return jsonify({
        "machine": machine.to_dict(),
        "public_key": signer.get_public_key(machine_id)
    })


@app.route('/relic/reserve', methods=['POST'])
def reserve_machine():
    """POST /relic/reserve - Reserve a machine"""
    data, error = _json_object_body()
    if error:
        return error
    
    required = ["machine_id", "agent_id", "duration_hours", "payment_rtc"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields", "required": required}), 400
    
    reservation, error = reservation_manager.create_reservation(
        machine_id=data["machine_id"],
        agent_id=data["agent_id"],
        duration_hours=data["duration_hours"],
        payment_rtc=data["payment_rtc"]
    )
    
    if error:
        return jsonify({"error": error}), 400
    
    return jsonify({
        "ok": True,
        "reservation": reservation.to_dict(),
        "message": "Reservation confirmed. Access credentials provided."
    }), 201


@app.route('/relic/reservation/<reservation_id>', methods=['GET'])
def get_reservation(reservation_id: str):
    """Get reservation details"""
    reservation = reservation_manager.get_reservation(reservation_id)
    if not reservation:
        return jsonify({"error": "Reservation not found"}), 404
    
    return jsonify({"reservation": reservation.to_dict()})


@app.route('/relic/reservation/<reservation_id>/start', methods=['POST'])
def start_reservation_session(reservation_id: str):
    """Start a reservation session"""
    error = reservation_manager.start_session(reservation_id)
    if error:
        return jsonify({"error": error}), 400
    
    reservation = reservation_manager.get_reservation(reservation_id)
    return jsonify({
        "ok": True,
        "status": "active",
        "access": {
            "ssh": reservation.ssh_credentials,
            "api_key": reservation.api_key
        },
        "expires_at": reservation.end_time
    })


@app.route('/relic/reservation/<reservation_id>/complete', methods=['POST'])
def complete_reservation_session(reservation_id: str):
    """Complete session and get provenance receipt"""
    data, error = _json_object_body()
    if error:
        return error
    
    required = ["compute_hash", "hardware_attestation"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields", "required": required}), 400
    
    receipt, error = reservation_manager.complete_session(
        reservation_id=reservation_id,
        compute_hash=data["compute_hash"],
        hardware_attestation=data["hardware_attestation"]
    )
    
    if error:
        return jsonify({"error": error}), 400
    
    return jsonify({
        "ok": True,
        "receipt": receipt.to_dict(),
        "message": "Session completed. Provenance receipt generated."
    })


@app.route('/relic/receipt/<session_id>', methods=['GET'])
def get_receipt(session_id: str):
    """GET /relic/receipt/<session_id> - Get provenance receipt"""
    receipt = reservation_manager.get_receipt(session_id)
    if not receipt:
        return jsonify({"error": "Receipt not found"}), 404
    
    # Verify signature
    is_valid = signer.verify_signature(
        {k: v for k, v in receipt.to_dict().items() if k != 'signature'},
        receipt.signature,
        receipt.machine_id
    )
    
    return jsonify({
        "receipt": receipt.to_dict(),
        "signature_valid": is_valid
    })


@app.route('/relic/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get most-rented machines leaderboard"""
    limit, error = _positive_limit()
    if error:
        return error
    leaderboard = reservation_manager.get_most_rented_machines(limit)
    
    machines_data = []
    for machine_id, count in leaderboard:
        machine = registry.get_machine(machine_id)
        if machine:
            machines_data.append({
                "machine_id": machine_id,
                "name": machine.name,
                "architecture": machine.architecture,
                "total_reservations": count,
                "hourly_rate_rtc": machine.hourly_rate_rtc
            })
    
    return jsonify({
        "leaderboard": machines_data,
        "timestamp": datetime.now().isoformat()
    })


@app.route('/relic/agent/<agent_id>/reservations', methods=['GET'])
def get_agent_reservations(agent_id: str):
    """Get all reservations for an agent"""
    reservations = reservation_manager.get_agent_reservations(agent_id)
    return jsonify({
        "agent_id": agent_id,
        "reservations": [r.to_dict() for r in reservations],
        "count": len(reservations)
    })


# ============== MCP Endpoints ==============

@app.route('/mcp/manifest', methods=['GET'])
def get_mcp_manifest():
    """Get MCP server manifest"""
    return jsonify(mcp.get_mcp_manifest())


@app.route('/mcp/tool', methods=['POST'])
def call_mcp_tool():
    """Call an MCP tool"""
    data, error = _json_object_body()
    if error:
        return error
    
    tool_name = data.get("tool")
    arguments = data.get("arguments", {})
    
    if not tool_name:
        return jsonify({"error": "Missing tool name"}), 400
    
    result = mcp.handle_tool_call(tool_name, arguments)
    return jsonify(result)


# ============== Beacon Endpoints ==============

@app.route('/beacon/message', methods=['POST'])
def handle_beacon_message():
    """Handle Beacon protocol message"""
    data, error = _json_object_body()
    if error:
        return error
    
    message_type = data.get("type")
    payload = data.get("payload", {})
    
    if not message_type:
        return jsonify({"error": "Missing message type"}), 400
    
    result = beacon.handle_message(message_type, payload)
    return jsonify(result)


# ============== BoTTube Integration ==============

@app.route('/bottube/badge/<session_id>', methods=['GET'])
def get_botube_badge(session_id: str):
    """Get BoTTube badge for relic-rendered video"""
    receipt = reservation_manager.get_receipt(session_id)
    if not receipt:
        return jsonify({"error": "Session not found"}), 404
    
    machine = registry.get_machine(receipt.machine_id)
    
    badge = {
        "badge_type": "relic_rendered",
        "session_id": session_id,
        "machine_name": machine.name if machine else "Unknown",
        "machine_architecture": machine.architecture if machine else "Unknown",
        "receipt_id": receipt.receipt_id,
        "render_date": datetime.fromtimestamp(receipt.session_end).isoformat(),
        "verification_hash": receipt.compute_hash[:16],
        "badge_url": f"/static/badges/relic-{session_id}.svg"
    }
    
    return jsonify(badge)


# ============== Static Files ==============

@app.route('/static/<path:filename>')
def serve_static(filename: str):
    """Serve static files"""
    from flask import send_from_directory
    return send_from_directory('static', filename)


# ============== Main ==============

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='RustChain Rent-a-Relic Market API')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    logger.info(f"Starting Relic Market API on {args.host}:{args.port}")
    logger.info(f"Registered {len(registry.list_machines())} vintage machines")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
