"""
Rent-a-Relic Market — Python Package
AI agents can book authenticated time on named vintage machines.
"""
__version__ = "0.1.0"
__author__ = "RustChain"

from .machine_registry import MachineRegistry, Machine
from .escrow import EscrowManager
from .provenance_receipt import ProvenanceReceipt
from .reservation_server import app

__all__ = [
    "MachineRegistry",
    "Machine",
    "EscrowManager",
    "ProvenanceReceipt",
    "app",
]
