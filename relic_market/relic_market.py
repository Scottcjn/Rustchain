"""
RustChain Rent-a-Relic Market
Book authenticated time on vintage machines through MCP and Beacon.
"""
import json
import time
import hashlib
import secrets
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List
from enum import Enum

DATA_DIR = Path("data/relic_market")
MACHINES_FILE = DATA_DIR / "machines.json"
RESERVATIONS_FILE = DATA_DIR / "reservations.json"
RECEIPTS_FILE = DATA_DIR / "receipts.json"
KEYSTORE_DIR = Path("data/relic_market/keystore")

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
KEYSTORE_DIR.mkdir(parents=True, exist_ok=True)


class SlotDuration(Enum):
    ONE_HOUR = 3600
    FOUR_HOURS = 14400
    TWENTY_FOUR_HOURS = 86400


@dataclass
class Machine:
    id: str
    name: str
    architecture: str
    specs: dict
    hourly_rate: float  # RTC per hour
    owner: str
    ssh_pubkey: str
    attestation_score: float  # 0.0 - 1.0
    total_sessions: int
    uptime_hours: float
    image_urls: List[str]
    description: str
    status: str = "available"  # available, booked, offline


@dataclass
class Reservation:
    id: str
    machine_id: str
    agent_id: str
    start_time: float
    end_time: float
    duration: int  # seconds
    cost_rtc: float
    status: str  # pending, active, completed, cancelled, disputed
    escrow_tx: Optional[str]
    ssh_credential: Optional[str]
    created_at: float


@dataclass
class ProvenanceReceipt:
    receipt_id: str
    machine_passport_id: str
    agent_id: str
    session_id: str
    start_time: float
    end_time: float
    duration_seconds: int
    output_hash: str  # hash of what was computed
    attestation_proof: dict
    machine_ed25519_pubkey: str
    signature: str  # Ed25519 signature
    reservation_id: str


# ---------------------------------------------------------------------------
# Machine Registry
# ---------------------------------------------------------------------------

def init_sample_machines():
    """Initialize with sample vintage machines."""
    if MACHINES_FILE.exists():
        return load_machines()
    
    machines = [
        Machine(
            id="power8-001",
            name="Blue Horizon",
            architecture="POWER8",
            specs={
                "cpu": "IBM POWER8 (10 cores @ 3.0 GHz)",
                "ram_gb": 512,
                "storage_tb": 4,
                "os": "Ubuntu 22.04 LTS",
                "special": "NVLink GPU enclosure"
            },
            hourly_rate=12.0,
            owner="scott",
            ssh_pubkey="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
            attestation_score=0.95,
            total_sessions=47,
            uptime_hours=1847.3,
            image_urls=["https://rustchain.org/machines/power8-001/front.jpg"],
            description="A powerful IBM POWER8 machine with exceptional attestation history. Located in Singapore.",
        ),
        Machine(
            id="g5-001",
            name="Quicksilver",
            architecture="G5",
            specs={
                "cpu": "PowerPC 970FX (8 cores @ 2.5 GHz)",
                "ram_gb": 64,
                "storage_gb": 2000,
                "os": "MacOS X 10.5 Leopard",
                "special": "Dual GPU (Radeon 9650)"
            },
            hourly_rate=8.0,
            owner="scott",
            ssh_pubkey="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
            attestation_score=0.88,
            total_sessions=23,
            uptime_hours=912.5,
            image_urls=["https://rustchain.org/machines/g5-001/side.jpg"],
            description="A rare G5 PowerMac running MacOS X Leopard. Perfect for vintage rendering.",
        ),
        Machine(
            id="sparc64-001",
            name="Solaris Ghost",
            architecture="SPARC64",
            specs={
                "cpu": "SPARC64 VII (4 cores @ 2.4 GHz)",
                "ram_gb": 256,
                "storage_tb": 2,
                "os": "Solaris 11",
                "special": "FMA instructions enabled"
            },
            hourly_rate=10.0,
            owner="scott",
            ssh_pubkey="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
            attestation_score=0.91,
            total_sessions=31,
            uptime_hours=1203.8,
            image_urls=["https://rustchain.org/machines/sparc64-001/panel.jpg"],
            description="SPARC64 machine with exceptional cryptographic performance for hash computations.",
        ),
        Machine(
            id="pi400-001",
            name="Pocket Time Capsule",
            architecture="ARM64",
            specs={
                "cpu": "Broadcom BCM2711 (4 cores @ 1.8 GHz)",
                "ram_gb": 8,
                "storage_gb": 512,
                "os": "Raspberry Pi OS 64-bit",
                "special": "GPIO breakout, PoE+"
            },
            hourly_rate=1.5,
            owner="scott",
            ssh_pubkey="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
            attestation_score=0.72,
            total_sessions=89,
            uptime_hours=3421.1,
            image_urls=["https://rustchain.org/machines/pi400-001/top.jpg"],
            description="Low-cost entry point for simple computation and testing.",
        ),
        Machine(
            id="mips-001",
            name="Router Eternal",
            architecture="MIPS",
            specs={
                "cpu": "MIPS64 20Kc (8 cores @ 1.2 GHz)",
                "ram_gb": 32,
                "storage_gb": 512,
                "os": "Debian 12 MIPS64",
                "special": "Netgear WNR8500 hardware"
            },
            hourly_rate=4.0,
            owner="scott",
            ssh_pubkey="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...",
            attestation_score=0.81,
            total_sessions=55,
            uptime_hours=2889.4,
            image_urls=["https://rustchain.org/machines/mips-001/board.jpg"],
            description="MIPS router repurposed as a compute node with excellent uptime record.",
        ),
    ]
    
    save_machines(machines)
    return machines


def load_machines() -> List[Machine]:
    if not MACHINES_FILE.exists():
        return init_sample_machines()
    with open(MACHINES_FILE) as f:
        data = json.load(f)
    return [Machine(**m) for m in data]


def save_machines(machines: List[Machine]):
    with open(MACHINES_FILE, "w") as f:
        json.dump([asdict(m) for m in machines], f, indent=2)


def get_available_machines() -> List[Machine]:
    machines = load_machines()
    return [m for m in machines if m.status == "available"]


def get_machine(machine_id: str) -> Optional[Machine]:
    machines = load_machines()
    for m in machines:
        if m.id == machine_id:
            return m
    return None


def register_machine(spec: dict) -> Machine:
    machine_id = hashlib.sha256(
        (spec["name"] + str(time.time())).encode()
    ).hexdigest()[:16]
    
    machine = Machine(
        id=machine_id,
        name=spec["name"],
        architecture=spec["architecture"],
        specs=spec["specs"],
        hourly_rate=spec["hourly_rate"],
        owner=spec["owner"],
        ssh_pubkey=spec["ssh_pubkey"],
        attestation_score=spec.get("attestation_score", 0.5),
        total_sessions=0,
        uptime_hours=0.0,
        image_urls=spec.get("image_urls", []),
        description=spec.get("description", ""),
        status="available",
    )
    
    machines = load_machines()
    machines.append(machine)
    save_machines(machines)
    return machine


# ---------------------------------------------------------------------------
# Reservation System
# ---------------------------------------------------------------------------

def load_reservations() -> List[Reservation]:
    if not RESERVATIONS_FILE.exists():
        return []
    with open(RESERVATIONS_FILE) as f:
        data = json.load(f)
    return [Reservation(**r) for r in data]


def save_reservations(reservations: List[Reservation]):
    with open(RESERVATIONS_FILE, "w") as f:
        json.dump([asdict(r) for r in reservations], f, indent=2)


def create_reservation(machine_id: str, agent_id: str, duration_hours: int) -> Reservation:
    """
    Create a reservation for a machine.
    Duration: 1, 4, or 24 hours.
    Payment locked in escrow.
    """
    machine = get_machine(machine_id)
    if not machine:
        raise ValueError(f"Machine {machine_id} not found")
    if machine.status != "available":
        raise ValueError(f"Machine {machine_id} is not available")
    
    if duration_hours not in [1, 4, 24]:
        raise ValueError("Duration must be 1, 4, or 24 hours")
    
    cost_rtc = machine.hourly_rate * duration_hours
    
    now = time.time()
    reservation = Reservation(
        id=secrets.token_hex(16),
        machine_id=machine_id,
        agent_id=agent_id,
        start_time=now,
        end_time=now + (duration_hours * 3600),
        duration=duration_hours * 3600,
        cost_rtc=cost_rtc,
        status="pending",
        escrow_tx=None,  # Would integrate with RTC payment contract
        ssh_credential=None,
        created_at=now,
    )
    
    # Lock machine
    machines = load_machines()
    for m in machines:
        if m.id == machine_id:
            m.status = "booked"
    save_machines(machines)
    
    reservations = load_reservations()
    reservations.append(reservation)
    save_reservations(reservations)
    
    return reservation


def activate_reservation(reservation_id: str, escrow_tx: str) -> Reservation:
    """Activate a reservation after escrow is confirmed."""
    reservations = load_reservations()
    for r in reservations:
        if r.id == reservation_id:
            r.status = "active"
            r.escrow_tx = escrow_tx
            r.start_time = time.time()
            r.end_time = time.time() + r.duration
            # Generate SSH credential
            r.ssh_credential = f"ssh relic@{r.machine_id}.rustchain.org -p {2222+hash(r.id)%1000}"
            save_reservations(reservations)
            return r
    raise ValueError(f"Reservation {reservation_id} not found")


def complete_reservation(reservation_id: str, output_hash: str, attestation: dict) -> ProvenanceReceipt:
    """Complete a session and generate provenance receipt."""
    reservations = load_reservations()
    for r in reservations:
        if r.id == reservation_id:
            r.status = "completed"
            save_reservations(reservations)
            
            # Free up the machine
            machines = load_machines()
            for m in machines:
                if m.id == r.machine_id:
                    m.status = "available"
                    m.total_sessions += 1
            save_machines(machines)
            
            # Generate receipt
            machine = get_machine(r.machine_id)
            receipt = ProvenanceReceipt(
                receipt_id=secrets.token_hex(16),
                machine_passport_id=r.machine_id,
                agent_id=r.agent_id,
                session_id=r.id,
                start_time=r.start_time,
                end_time=time.time(),
                duration_seconds=int(time.time() - r.start_time),
                output_hash=output_hash,
                attestation_proof=attestation,
                machine_ed25519_pubkey=machine.ssh_pubkey if machine else "unknown",
                signature="",  # Would be signed with machine's Ed25519 key
                reservation_id=r.id,
            )
            
            # Save receipt
            receipts = load_receipts()
            receipts.append(receipt)
            save_receipts(receipts)
            
            return receipt
    
    raise ValueError(f"Reservation {reservation_id} not found")


def cancel_reservation(reservation_id: str) -> bool:
    """Cancel a reservation and release the machine."""
    reservations = load_reservations()
    for r in reservations:
        if r.id == reservation_id:
            if r.status in ("completed", "cancelled"):
                return False
            r.status = "cancelled"
            save_reservations(reservations)
            
            # Free machine
            machines = load_machines()
            for m in machines:
                if m.id == r.machine_id:
                    m.status = "available"
            save_machines(machines)
            return True
    return False


def load_receipts() -> List[ProvenanceReceipt]:
    if not RECEIPTS_FILE.exists():
        return []
    with open(RECEIPTS_FILE) as f:
        data = json.load(f)
    return [ProvenanceReceipt(**r) for r in data]


def save_receipts(receipts: List[ProvenanceReceipt]):
    with open(RECEIPTS_FILE, "w") as f:
        json.dump([asdict(r) for r in receipts], f, indent=2, default=str)


def get_receipt(receipt_id: str) -> Optional[ProvenanceReceipt]:
    receipts = load_receipts()
    for r in receipts:
        if r.receipt_id == receipt_id:
            return r
    return None


def get_machine_receipts(machine_id: str) -> List[ProvenanceReceipt]:
    receipts = load_receipts()
    return [r for r in receipts if r.machine_passport_id == machine_id]


# ---------------------------------------------------------------------------
# API Endpoints (Flask-compatible)
# ---------------------------------------------------------------------------

API_PREFIX = "/relic"


def get_routes():
    return [
        (f"{API_PREFIX}/machines", "GET", list_machines),
        (f"{API_PREFIX}/available", "GET", list_available),
        (f"{API_PREFIX}/<machine_id>", "GET", get_machine_info),
        (f"{API_PREFIX}/reserve", "POST", create_reservation_endpoint),
        (f"{API_PREFIX}/receipt/<receipt_id>", "GET", get_receipt_endpoint),
        (f"{API_PREFIX}/machine/<machine_id>/receipts", "GET", get_machine_receipts_endpoint),
    ]


def list_machines(_=None):
    machines = load_machines()
    return {
        "machines": [asdict(m) for m in machines],
        "total": len(machines),
    }


def list_available(_=None):
    machines = get_available_machines()
    return {
        "machines": [asdict(m) for m in machines],
        "count": len(machines),
    }


def get_machine_info(_, machine_id):
    machine = get_machine(machine_id)
    if not machine:
        return {"error": "Machine not found"}, 404
    receipts = get_machine_receipts(machine_id)
    return {
        **asdict(machine),
        "receipts": [asdict(r) for r in receipts[-10:]],
    }


def create_reservation_endpoint(body_data):
    machine_id = body_data["machine_id"]
    agent_id = body_data["agent_id"]
    duration_hours = int(body_data["duration_hours"])
    reservation = create_reservation(machine_id, agent_id, duration_hours)
    return {"reservation": asdict(reservation)}


def get_receipt_endpoint(environ, receipt_id):
    receipt = get_receipt(receipt_id)
    if not receipt:
        return {"error": "Receipt not found"}, 404
    return {"receipt": asdict(receipt)}


def get_machine_receipts_endpoint(environ, machine_id):
    receipts = get_machine_receipts(machine_id)
    return {"receipts": [asdict(r) for r in receipts]}


# ---------------------------------------------------------------------------
# Flask API Server
# ---------------------------------------------------------------------------

try:
    from flask import Flask, jsonify, request
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False
    print("Flask not installed. Run: pip install flask")
    print("Starting in demo mode (data persisted to data/relic_market/)")


def create_app():
    if not HAS_FLASK:
        raise ImportError("Flask required: pip install flask")
    app = Flask(__name__)
    
    @app.route("/api/relic/machines", methods=["GET"])
    def api_list_machines():
        return jsonify(list_machines({}))
    
    @app.route("/api/relic/available", methods=["GET"])
    def api_list_available():
        return jsonify(list_available({}))
    
    @app.route("/api/relic/<machine_id>", methods=["GET"])
    def api_get_machine(machine_id):
        result = get_machine_info({}, machine_id)
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result)
    
    @app.route("/api/relic/reserve", methods=["POST"])
    def api_reserve():
        body = request.json
        try:
            reservation = create_reservation(
                body["machine_id"],
                body["agent_id"],
                int(body["duration_hours"])
            )
            return jsonify({"reservation": asdict(reservation)})
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
    
    @app.route("/api/relic/receipt/<receipt_id>", methods=["GET"])
    def api_get_receipt(receipt_id):
        receipt_obj = get_receipt(receipt_id)
        if not receipt_obj:
            return jsonify({"error": "Receipt not found"}), 404
        return jsonify({"receipt": asdict(receipt_obj)})
    
    @app.route("/api/relic/machine/<machine_id>/receipts", methods=["GET"])
    def api_machine_receipts(machine_id):
        receipts = get_machine_receipts(machine_id)
        return jsonify({"receipts": [asdict(r) for r in receipts]})
    
    return app


if __name__ == "__main__":
    init_sample_machines()
    print("Rent-a-Relic Market initialized.")
    print(f"Machines: {len(load_machines())}")
    print(f"Available: {len(get_available_machines())}")
    
    if HAS_FLASK:
        app = create_app()
        print("Starting Flask server on http://localhost:8080")
        app.run(host="0.0.0.0", port=8080, debug=True)
    else:
        print("Demo mode - data saved to data/relic_market/")
