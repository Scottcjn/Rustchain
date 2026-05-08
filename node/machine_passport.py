#!/usr/bin/env python3
"""
Machine Passport Ledger — Give Every Relic a Biography

This module implements an on-chain passport format for individual relic machines,
tracking their hardware identity, repair history, benchmark signatures, and lineage.

Issue: #2309
Bounty: 70 RTC (+ 20 RTC bonus for PDF + QR)
"""

import os
import sys
import json
import time
import hashlib
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Try to import optional dependencies
try:
    import qrcode
    HAVE_QRCODE = True
except ImportError:
    HAVE_QRCODE = False
    print("[WARN] qrcode library not available - QR code generation disabled")

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    HAVE_REPORTLAB = True
except ImportError:
    HAVE_REPORTLAB = False
    print("[WARN] reportlab library not available - PDF generation disabled")


@dataclass
class MachinePassport:
    """Data structure for a machine passport."""
    
    machine_id: str  # Hardware fingerprint hash
    name: str  # Human-given name (e.g., "Old Faithful")
    owner_miner_id: str  # Current owner/miner operator
    manufacture_year: Optional[int] = None  # Estimated from ROM/CPU stepping
    architecture: Optional[str] = None  # G4, G5, SPARC, MIPS, etc.
    photo_hash: Optional[str] = None  # IPFS or BoTTube link to machine photo
    photo_url: Optional[str] = None  # Direct URL to photo
    provenance: Optional[str] = None  # How acquired (eBay, pawn shop, etc.)
    created_at: int = 0  # Unix timestamp
    updated_at: int = 0  # Unix timestamp
    
    # Computed fields (not stored directly)
    repair_log: List[Dict] = None
    attestation_history: List[Dict] = None
    benchmark_signatures: List[Dict] = None
    lineage_notes: List[Dict] = None
    
    def __post_init__(self):
        if self.repair_log is None:
            self.repair_log = []
        if self.attestation_history is None:
            self.attestation_history = []
        if self.benchmark_signatures is None:
            self.benchmark_signatures = []
        if self.lineage_notes is None:
            self.lineage_notes = []
        if self.created_at == 0:
            self.created_at = int(time.time())
        if self.updated_at == 0:
            self.updated_at = int(time.time())
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'machine_id': self.machine_id,
            'name': self.name,
            'owner_miner_id': self.owner_miner_id,
            'manufacture_year': self.manufacture_year,
            'architecture': self.architecture,
            'photo_hash': self.photo_hash,
            'photo_url': self.photo_url,
            'provenance': self.provenance,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MachinePassport':
        """Create from dictionary."""
        return cls(
            machine_id=data.get('machine_id', ''),
            name=data.get('name', ''),
            owner_miner_id=data.get('owner_miner_id', ''),
            manufacture_year=data.get('manufacture_year'),
            architecture=data.get('architecture'),
            photo_hash=data.get('photo_hash'),
            photo_url=data.get('photo_url'),
            provenance=data.get('provenance'),
            created_at=data.get('created_at', int(time.time())),
            updated_at=data.get('updated_at', int(time.time())),
        )


def compute_machine_id(fingerprint_data: Dict) -> str:
    """
    Compute a unique machine ID from hardware fingerprint data.
    
    Args:
        fingerprint_data: Dict containing hardware identifiers
        
    Returns:
        SHA-256 hash of sorted fingerprint data
    """
    # Sort keys for deterministic hashing
    sorted_data = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]


def init_machine_passport_schema(conn: sqlite3.Connection) -> None:
    """
    Initialize the machine passport ledger database schema.
    
    Creates the following tables:
    - machine_passports: Core passport data
    - passport_repair_log: Repair and maintenance history
    - passport_attestation_history: Attestation records
    - passport_benchmark_signatures: Performance benchmarks
    - passport_lineage_notes: Ownership transfers and lineage
    """
    conn.executescript("""
        -- Core passport table
        CREATE TABLE IF NOT EXISTS machine_passports (
            machine_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_miner_id TEXT NOT NULL,
            manufacture_year INTEGER,
            architecture TEXT,
            photo_hash TEXT,
            photo_url TEXT,
            provenance TEXT,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );
        
        -- Repair log table
        CREATE TABLE IF NOT EXISTS passport_repair_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            repair_date INTEGER NOT NULL,
            repair_type TEXT NOT NULL,
            description TEXT NOT NULL,
            parts_replaced TEXT,
            technician TEXT,
            cost_rtc INTEGER,
            notes TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machine_passports(machine_id)
        );
        
        -- Attestation history table
        CREATE TABLE IF NOT EXISTS passport_attestation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            attestation_ts INTEGER NOT NULL,
            epoch INTEGER,
            total_epochs INTEGER,
            total_rtc_earned INTEGER,
            benchmark_hash TEXT,
            entropy_score REAL,
            hardware_binding TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machine_passports(machine_id)
        );
        
        -- Benchmark signatures table
        CREATE TABLE IF NOT EXISTS passport_benchmark_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            benchmark_ts INTEGER NOT NULL,
            cache_timing_profile TEXT,
            simd_identity TEXT,
            thermal_curve TEXT,
            memory_bandwidth REAL,
            compute_score REAL,
            entropy_throughput REAL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machine_passports(machine_id)
        );
        
        -- Lineage notes table
        CREATE TABLE IF NOT EXISTS passport_lineage_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            lineage_ts INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            from_owner TEXT,
            to_owner TEXT,
            description TEXT,
            tx_hash TEXT,
            created_at INTEGER NOT NULL,
            FOREIGN KEY (machine_id) REFERENCES machine_passports(machine_id)
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_passport_owner ON machine_passports(owner_miner_id);
        CREATE INDEX IF NOT EXISTS idx_passport_arch ON machine_passports(architecture);
        CREATE INDEX IF NOT EXISTS idx_passport_year ON machine_passports(manufacture_year);
        
        CREATE INDEX IF NOT EXISTS idx_repair_machine ON passport_repair_log(machine_id);
        CREATE INDEX IF NOT EXISTS idx_repair_date ON passport_repair_log(repair_date);
        
        CREATE INDEX IF NOT EXISTS idx_attest_machine ON passport_attestation_history(machine_id);
        CREATE INDEX IF NOT EXISTS idx_attest_ts ON passport_attestation_history(attestation_ts);
        
        CREATE INDEX IF NOT EXISTS idx_bench_machine ON passport_benchmark_signatures(machine_id);
        CREATE INDEX IF NOT EXISTS idx_bench_ts ON passport_benchmark_signatures(benchmark_ts);
        
        CREATE INDEX IF NOT EXISTS idx_lineage_machine ON passport_lineage_notes(machine_id);
        CREATE INDEX IF NOT EXISTS idx_lineage_ts ON passport_lineage_notes(lineage_ts);
    """)
    conn.commit()


class MachinePassportLedger:
    """
    Manages the machine passport ledger for relic machines.
    
    Provides CRUD operations for machine passports, repair logs,
    attestation history, benchmark signatures, and lineage notes.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the ledger with a database path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_schema()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_schema(self) -> None:
        """Ensure the database schema is initialized."""
        with self._get_connection() as conn:
            init_machine_passport_schema(conn)
    
    # === Core Passport Operations ===
    
    def create_passport(self, passport: MachinePassport) -> Tuple[bool, str]:
        """
        Create a new machine passport.
        
        Args:
            passport: MachinePassport object
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO machine_passports 
                    (machine_id, name, owner_miner_id, manufacture_year, architecture,
                     photo_hash, photo_url, provenance, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    passport.machine_id,
                    passport.name,
                    passport.owner_miner_id,
                    passport.manufacture_year,
                    passport.architecture,
                    passport.photo_hash,
                    passport.photo_url,
                    passport.provenance,
                    passport.created_at,
                    passport.updated_at,
                ))
                conn.commit()
                return True, f"Passport created for machine {passport.machine_id}"
        except sqlite3.IntegrityError as e:
            return False, f"Passport already exists: {e}"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def get_passport(self, machine_id: str) -> Optional[MachinePassport]:
        """
        Retrieve a machine passport by ID.
        
        Args:
            machine_id: The machine's unique identifier
            
        Returns:
            MachinePassport or None if not found
        """
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM machine_passports WHERE machine_id = ?
            """, (machine_id,)).fetchone()
            
            if row:
                return MachinePassport(
                    machine_id=row['machine_id'],
                    name=row['name'],
                    owner_miner_id=row['owner_miner_id'],
                    manufacture_year=row['manufacture_year'],
                    architecture=row['architecture'],
                    photo_hash=row['photo_hash'],
                    photo_url=row['photo_url'],
                    provenance=row['provenance'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                )
            return None
    
    def update_passport(self, machine_id: str, updates: Dict) -> Tuple[bool, str]:
        """
        Update a machine passport.
        
        Args:
            machine_id: The machine's unique identifier
            updates: Dict of fields to update
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        allowed_fields = {'name', 'owner_miner_id', 'manufacture_year', 
                         'architecture', 'photo_hash', 'photo_url', 'provenance'}
        
        # Filter to allowed fields
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            return False, "No valid fields to update"
        
        # Build UPDATE statement
        set_clauses = [f"{field} = ?" for field in filtered_updates.keys()]
        set_clauses.append("updated_at = ?")
        values = list(filtered_updates.values()) + [int(time.time())]
        values.append(machine_id)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(f"""
                    UPDATE machine_passports 
                    SET {', '.join(set_clauses)}
                    WHERE machine_id = ?
                """, values)
                conn.commit()
                
                if cursor.rowcount == 0:
                    return False, "Passport not found"
                return True, f"Passport updated for machine {machine_id}"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def delete_passport(self, machine_id: str) -> Tuple[bool, str]:
        """
        Delete a machine passport (admin operation).
        
        Args:
            machine_id: The machine's unique identifier
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with self._get_connection() as conn:
                # Delete related records first
                conn.execute("DELETE FROM passport_repair_log WHERE machine_id = ?", (machine_id,))
                conn.execute("DELETE FROM passport_attestation_history WHERE machine_id = ?", (machine_id,))
                conn.execute("DELETE FROM passport_benchmark_signatures WHERE machine_id = ?", (machine_id,))
                conn.execute("DELETE FROM passport_lineage_notes WHERE machine_id = ?", (machine_id,))
                
                cursor = conn.execute("""
                    DELETE FROM machine_passports WHERE machine_id = ?
                """, (machine_id,))
                conn.commit()
                
                if cursor.rowcount == 0:
                    return False, "Passport not found"
                return True, f"Passport deleted for machine {machine_id}"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def list_passports(self, owner_miner_id: Optional[str] = None, 
                       architecture: Optional[str] = None,
                       limit: int = 100, offset: int = 0) -> List[MachinePassport]:
        """
        List machine passports with optional filtering.
        
        Args:
            owner_miner_id: Filter by owner
            architecture: Filter by architecture type
            limit: Maximum results to return
            offset: Pagination offset
            
        Returns:
            List of MachinePassport objects
        """
        conditions = []
        params = []
        
        if owner_miner_id:
            conditions.append("owner_miner_id = ?")
            params.append(owner_miner_id)
        
        if architecture:
            conditions.append("architecture = ?")
            params.append(architecture)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            rows = conn.execute(f"""
                SELECT * FROM machine_passports 
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, params).fetchall()
            
            return [MachinePassport(
                machine_id=row['machine_id'],
                name=row['name'],
                owner_miner_id=row['owner_miner_id'],
                manufacture_year=row['manufacture_year'],
                architecture=row['architecture'],
                photo_hash=row['photo_hash'],
                photo_url=row['photo_url'],
                provenance=row['provenance'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
            ) for row in rows]
    
    # === Repair Log Operations ===
    
    def add_repair_entry(self, machine_id: str, repair_date: int, repair_type: str,
                        description: str, parts_replaced: Optional[str] = None,
                        technician: Optional[str] = None, cost_rtc: Optional[int] = None,
                        notes: Optional[str] = None) -> Tuple[bool, str]:
        """Add a repair log entry."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO passport_repair_log 
                    (machine_id, repair_date, repair_type, description, parts_replaced,
                     technician, cost_rtc, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, repair_date, repair_type, description,
                    parts_replaced, technician, cost_rtc, notes, int(time.time())
                ))
                conn.commit()
                return True, "Repair entry added"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def get_repair_log(self, machine_id: str) -> List[Dict]:
        """Get repair log for a machine."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM passport_repair_log 
                WHERE machine_id = ?
                ORDER BY repair_date DESC
            """, (machine_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # === Attestation History Operations ===
    
    def add_attestation(self, machine_id: str, attestation_ts: int, epoch: Optional[int] = None,
                       total_epochs: Optional[int] = None, total_rtc_earned: Optional[int] = None,
                       benchmark_hash: Optional[str] = None, entropy_score: Optional[float] = None,
                       hardware_binding: Optional[str] = None) -> Tuple[bool, str]:
        """Add an attestation record."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO passport_attestation_history 
                    (machine_id, attestation_ts, epoch, total_epochs, total_rtc_earned,
                     benchmark_hash, entropy_score, hardware_binding, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, attestation_ts, epoch, total_epochs, total_rtc_earned,
                    benchmark_hash, entropy_score, hardware_binding, int(time.time())
                ))
                conn.commit()
                return True, "Attestation recorded"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def get_attestation_history(self, machine_id: str) -> List[Dict]:
        """Get attestation history for a machine."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM passport_attestation_history 
                WHERE machine_id = ?
                ORDER BY attestation_ts DESC
            """, (machine_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # === Benchmark Signatures Operations ===
    
    def add_benchmark(self, machine_id: str, benchmark_ts: int,
                     cache_timing_profile: Optional[str] = None,
                     simd_identity: Optional[str] = None,
                     thermal_curve: Optional[str] = None,
                     memory_bandwidth: Optional[float] = None,
                     compute_score: Optional[float] = None,
                     entropy_throughput: Optional[float] = None) -> Tuple[bool, str]:
        """Add a benchmark signature."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO passport_benchmark_signatures 
                    (machine_id, benchmark_ts, cache_timing_profile, simd_identity,
                     thermal_curve, memory_bandwidth, compute_score, entropy_throughput, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, benchmark_ts, cache_timing_profile, simd_identity,
                    thermal_curve, memory_bandwidth, compute_score, entropy_throughput,
                    int(time.time())
                ))
                conn.commit()
                return True, "Benchmark recorded"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def get_benchmark_signatures(self, machine_id: str) -> List[Dict]:
        """Get benchmark signatures for a machine."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM passport_benchmark_signatures 
                WHERE machine_id = ?
                ORDER BY benchmark_ts DESC
            """, (machine_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # === Lineage Notes Operations ===
    
    def add_lineage_note(self, machine_id: str, lineage_ts: int, event_type: str,
                        from_owner: Optional[str] = None, to_owner: Optional[str] = None,
                        description: Optional[str] = None, 
                        tx_hash: Optional[str] = None) -> Tuple[bool, str]:
        """Add a lineage note."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO passport_lineage_notes 
                    (machine_id, lineage_ts, event_type, from_owner, to_owner,
                     description, tx_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    machine_id, lineage_ts, event_type, from_owner, to_owner,
                    description, tx_hash, int(time.time())
                ))
                conn.commit()
                return True, "Lineage note added"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def get_lineage_notes(self, machine_id: str) -> List[Dict]:
        """Get lineage notes for a machine."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM passport_lineage_notes 
                WHERE machine_id = ?
                ORDER BY lineage_ts DESC
            """, (machine_id,)).fetchall()
            
            return [dict(row) for row in rows]
    
    # === Full Passport Export ===
    
    def export_passport_full(self, machine_id: str) -> Optional[Dict]:
        """
        Export complete passport data including all history.
        
        Args:
            machine_id: The machine's unique identifier
            
        Returns:
            Complete passport data as dict or None if not found
        """
        passport = self.get_passport(machine_id)
        if not passport:
            return None
        
        return {
            'passport': passport.to_dict(),
            'repair_log': self.get_repair_log(machine_id),
            'attestation_history': self.get_attestation_history(machine_id),
            'benchmark_signatures': self.get_benchmark_signatures(machine_id),
            'lineage_notes': self.get_lineage_notes(machine_id),
            'exported_at': int(time.time()),
        }


def generate_qr_code(passport_url: str, output_path: str) -> Tuple[bool, str]:
    """
    Generate a QR code linking to the machine's passport.
    
    Args:
        passport_url: URL to the passport viewer
        output_path: Path to save the QR code image
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not HAVE_QRCODE:
        return False, "qrcode library not available"
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(passport_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(output_path)
        return True, f"QR code saved to {output_path}"
    except Exception as e:
        return False, f"QR code generation failed: {e}"


def generate_passport_pdf(passport_data: Dict, output_path: str) -> Tuple[bool, str]:
    """
    Generate a printable PDF passport with vintage computer aesthetic.
    
    Args:
        passport_data: Complete passport data from export_passport_full()
        output_path: Path to save the PDF
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not HAVE_REPORTLAB:
        return False, "reportlab library not available"
    
    try:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Vintage computer aesthetic styles
        title_style = ParagraphStyle(
            'VintageTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            spaceAfter=12,
            alignment=TA_CENTER,
        )
        
        subtitle_style = ParagraphStyle(
            'VintageSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#7F8C8D'),
            spaceAfter=6,
        )
        
        # Header
        passport = passport_data.get('passport', {})
        elements.append(Paragraph("🔧 MACHINE PASSPORT", title_style))
        elements.append(Paragraph(f"RustChain Relic Registry", subtitle_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Machine details table
        details_data = [
            ['Machine ID:', passport.get('machine_id', 'N/A')[:20] + '...' if len(passport.get('machine_id', '')) > 20 else passport.get('machine_id', 'N/A')],
            ['Name:', passport.get('name', 'N/A')],
            ['Owner:', passport.get('owner_miner_id', 'N/A')],
            ['Architecture:', passport.get('architecture', 'N/A')],
            ['Manufacture Year:', str(passport.get('manufacture_year', 'N/A'))],
            ['Provenance:', passport.get('provenance', 'N/A')],
        ]
        
        details_table = Table(details_data, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ECF0F1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements.append(details_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Repair history
        elements.append(Paragraph("📋 REPAIR HISTORY", styles['Heading2']))
        repair_log = passport_data.get('repair_log', [])
        if repair_log:
            repair_data = [['Date', 'Type', 'Description', 'Parts']]
            for entry in repair_log[:10]:  # Limit to 10 entries
                repair_date = datetime.fromtimestamp(entry['repair_date']).strftime('%Y-%m-%d')
                repair_data.append([
                    repair_date,
                    entry['repair_type'],
                    entry['description'][:40] + '...' if len(entry['description']) > 40 else entry['description'],
                    entry.get('parts_replaced', 'N/A') or 'N/A',
                ])
            
            repair_table = Table(repair_data, colWidths=[1*inch, 1*inch, 3*inch, 1.5*inch])
            repair_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(repair_table)
        else:
            elements.append(Paragraph("No repair history recorded.", styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Attestation summary
        elements.append(Paragraph("✅ ATTESTATION HISTORY", styles['Heading2']))
        attestations = passport_data.get('attestation_history', [])
        if attestations:
            total_epochs = max((a.get('total_epochs', 0) for a in attestations), default=0)
            total_rtc = max((a.get('total_rtc_earned', 0) for a in attestations), default=0)
            elements.append(Paragraph(f"Total Epochs: {total_epochs}", styles['Normal']))
            elements.append(Paragraph(f"Total RTC Earned: {total_rtc / 1_000_000:.6f}", styles['Normal']))
            elements.append(Paragraph(f"Attestations: {len(attestations)}", styles['Normal']))
        else:
            elements.append(Paragraph("No attestation history.", styles['Normal']))
        
        elements.append(Spacer(1, 0.3*inch))
        
        # Footer
        elements.append(Spacer(1, 0.5*inch))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#95A5A6'),
            alignment=TA_CENTER,
        )
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | RustChain Machine Passport", footer_style))
        
        doc.build(elements)
        return True, f"PDF saved to {output_path}"
    except Exception as e:
        return False, f"PDF generation failed: {e}"


# CLI interface
def main():
    """Command-line interface for machine passport management."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Machine Passport Ledger CLI')
    parser.add_argument('--db', default='machine_passports.db', help='Database path')
    parser.add_argument('--action', required=True, 
                       choices=['create', 'get', 'update', 'list', 'add-repair', 
                               'add-attestation', 'add-benchmark', 'add-lineage',
                               'export', 'generate-qr', 'generate-pdf'],
                       help='Action to perform')
    parser.add_argument('--machine-id', help='Machine ID')
    parser.add_argument('--name', help='Machine name')
    parser.add_argument('--owner', help='Owner miner ID')
    parser.add_argument('--architecture', help='CPU architecture')
    parser.add_argument('--year', type=int, help='Manufacture year')
    parser.add_argument('--provenance', help='Acquisition source')
    parser.add_argument('--photo-url', help='Photo URL')
    parser.add_argument('--data', help='JSON data for complex operations')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    ledger = MachinePassportLedger(args.db)
    
    if args.action == 'create':
        if not all([args.machine_id, args.name, args.owner]):
            print("Error: --machine-id, --name, and --owner are required")
            sys.exit(1)
        
        passport = MachinePassport(
            machine_id=args.machine_id,
            name=args.name,
            owner_miner_id=args.owner,
            architecture=args.architecture,
            manufacture_year=args.year,
            provenance=args.provenance,
            photo_url=args.photo_url,
        )
        
        success, msg = ledger.create_passport(passport)
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'get':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        passport = ledger.get_passport(args.machine_id)
        if passport:
            print(json.dumps(passport.to_dict(), indent=2))
        else:
            print("Passport not found")
            sys.exit(1)
    
    elif args.action == 'list':
        passports = ledger.list_passports(
            owner_miner_id=args.owner if args.owner else None,
            architecture=args.architecture if args.architecture else None,
        )
        print(json.dumps([p.to_dict() for p in passports], indent=2))
    
    elif args.action == 'update':
        if not args.machine_id or not args.data:
            print("Error: --machine-id and --data required")
            sys.exit(1)
        
        try:
            updates = json.loads(args.data)
        except (json.JSONDecodeError, TypeError):
            updates = {}
        success, msg = ledger.update_passport(args.machine_id, updates)
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'add-repair':
        if not args.machine_id or not args.data:
            print("Error: --machine-id and --data required")
            sys.exit(1)
        
        data = json.loads(args.data)
        success, msg = ledger.add_repair_entry(
            machine_id=args.machine_id,
            repair_date=data.get('repair_date', int(time.time())),
            repair_type=data.get('repair_type', 'maintenance'),
            description=data.get('description', ''),
            parts_replaced=data.get('parts_replaced'),
            technician=data.get('technician'),
            cost_rtc=data.get('cost_rtc'),
            notes=data.get('notes'),
        )
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'add-attestation':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        try:
            data = json.loads(args.data) if args.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        success, msg = ledger.add_attestation(
            machine_id=args.machine_id,
            attestation_ts=data.get('attestation_ts', int(time.time())),
            epoch=data.get('epoch'),
            total_epochs=data.get('total_epochs'),
            total_rtc_earned=data.get('total_rtc_earned'),
            benchmark_hash=data.get('benchmark_hash'),
            entropy_score=data.get('entropy_score'),
            hardware_binding=data.get('hardware_binding'),
        )
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'add-benchmark':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        try:
            data = json.loads(args.data) if args.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}
        success, msg = ledger.add_benchmark(
            machine_id=args.machine_id,
            benchmark_ts=data.get('benchmark_ts', int(time.time())),
            cache_timing_profile=data.get('cache_timing_profile'),
            simd_identity=data.get('simd_identity'),
            thermal_curve=data.get('thermal_curve'),
            memory_bandwidth=data.get('memory_bandwidth'),
            compute_score=data.get('compute_score'),
            entropy_throughput=data.get('entropy_throughput'),
        )
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'add-lineage':
        if not args.machine_id or not args.data:
            print("Error: --machine-id and --data required")
            sys.exit(1)
        
        data = json.loads(args.data)
        success, msg = ledger.add_lineage_note(
            machine_id=args.machine_id,
            lineage_ts=data.get('lineage_ts', int(time.time())),
            event_type=data.get('event_type', 'transfer'),
            from_owner=data.get('from_owner'),
            to_owner=data.get('to_owner'),
            description=data.get('description'),
            tx_hash=data.get('tx_hash'),
        )
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'export':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        data = ledger.export_passport_full(args.machine_id)
        if data:
            output = args.output or f"{args.machine_id}_passport.json"
            with open(output, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Passport exported to {output}")
        else:
            print("Passport not found")
            sys.exit(1)
    
    elif args.action == 'generate-qr':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        passport_url = f"https://rustchain.org/passport/{args.machine_id}"
        output = args.output or f"{args.machine_id}_qr.png"
        success, msg = generate_qr_code(passport_url, output)
        print(f"{'✓' if success else '✗'} {msg}")
        sys.exit(0 if success else 1)
    
    elif args.action == 'generate-pdf':
        if not args.machine_id:
            print("Error: --machine-id required")
            sys.exit(1)
        
        data = ledger.export_passport_full(args.machine_id)
        if data:
            output = args.output or f"{args.machine_id}_passport.pdf"
            success, msg = generate_passport_pdf(data, output)
            print(f"{'✓' if success else '✗'} {msg}")
            sys.exit(0 if success else 1)
        else:
            print("Passport not found")
            sys.exit(1)


if __name__ == '__main__':
    main()
