#!/usr/bin/env python3
"""
Machine Passport Ledger API Routes

RESTful API endpoints for machine passport management.
Integrates with Flask applications.

Issue: #2309
"""

import os
import json
import time
import hmac
from typing import Optional
from flask import Blueprint, request, jsonify, render_template_string

from machine_passport import (
    MachinePassportLedger,
    MachinePassport,
    compute_machine_id,
    generate_qr_code,
    generate_passport_pdf,
)

# Create blueprint
machine_passport_bp = Blueprint('machine_passport', __name__, url_prefix='/api/machine-passport')

# Database path from environment
PASSPORT_DB_PATH = os.environ.get('PASSPORT_DB_PATH', 'machine_passports.db')

# Ledger instance (lazy initialization)
_ledger: Optional[MachinePassportLedger] = None


def get_ledger() -> MachinePassportLedger:
    """Get or create the ledger instance."""
    global _ledger
    if _ledger is None:
        _ledger = MachinePassportLedger(PASSPORT_DB_PATH)
    return _ledger


def get_optional_json_object():
    """Return an optional JSON object body or an error response."""
    data = request.get_json(silent=True)
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, (jsonify({
            'ok': False,
            'error': 'invalid_request',
            'message': 'JSON object required',
        }), 400)
    return data, None


def _require_admin(req):
    """Validate admin authentication for machine passport write endpoints."""
    expected_admin_key = os.environ.get('ADMIN_KEY', '').strip()
    provided_admin_key = (
        req.headers.get('X-Admin-Key', '') or req.headers.get('X-API-Key', '')
    ).strip()

    if not expected_admin_key:
        return jsonify({
            'ok': False,
            'error': 'admin_key_not_configured',
            'message': 'ADMIN_KEY not configured - write endpoint disabled',
        }), 503

    if not provided_admin_key or not hmac.compare_digest(provided_admin_key, expected_admin_key):
        return jsonify({
            'ok': False,
            'error': 'unauthorized',
            'message': 'Admin key required',
        }), 401

    return None


# === Public Read Endpoints ===

@machine_passport_bp.route('/<machine_id>', methods=['GET'])
def get_passport(machine_id: str):
    """
    Get a machine passport by ID.
    
    Returns complete passport data including repair log,
    attestation history, benchmark signatures, and lineage notes.
    """
    ledger = get_ledger()
    data = ledger.export_passport_full(machine_id)
    
    if data:
        return jsonify({
            'ok': True,
            'passport': data,
        })
    else:
        return jsonify({
            'ok': False,
            'error': 'passport_not_found',
            'message': f'No passport found for machine {machine_id}',
        }), 404


@machine_passport_bp.route('', methods=['GET'])
def list_passports():
    """
    List machine passports with optional filtering.
    
    Query Parameters:
    - owner: Filter by owner miner ID
    - architecture: Filter by CPU architecture
    - limit: Maximum results (default: 100, max: 500)
    - offset: Pagination offset (default: 0)
    """
    ledger = get_ledger()
    
    owner = request.args.get('owner')
    architecture = request.args.get('architecture')
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    
    passports = ledger.list_passports(
        owner_miner_id=owner,
        architecture=architecture,
        limit=limit,
        offset=offset,
    )
    
    return jsonify({
        'ok': True,
        'count': len(passports),
        'passports': [p.to_dict() for p in passports],
        'limit': limit,
        'offset': offset,
    })


@machine_passport_bp.route('/<machine_id>/repair-log', methods=['GET'])
def get_repair_log(machine_id: str):
    """Get repair log for a machine."""
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    return jsonify({
        'ok': True,
        'machine_id': machine_id,
        'repair_log': ledger.get_repair_log(machine_id),
    })


@machine_passport_bp.route('/<machine_id>/attestations', methods=['GET'])
def get_attestations(machine_id: str):
    """Get attestation history for a machine."""
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    return jsonify({
        'ok': True,
        'machine_id': machine_id,
        'attestations': ledger.get_attestation_history(machine_id),
    })


@machine_passport_bp.route('/<machine_id>/benchmarks', methods=['GET'])
def get_benchmarks(machine_id: str):
    """Get benchmark signatures for a machine."""
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    return jsonify({
        'ok': True,
        'machine_id': machine_id,
        'benchmarks': ledger.get_benchmark_signatures(machine_id),
    })


@machine_passport_bp.route('/<machine_id>/lineage', methods=['GET'])
def get_lineage(machine_id: str):
    """Get lineage notes for a machine."""
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    return jsonify({
        'ok': True,
        'machine_id': machine_id,
        'lineage': ledger.get_lineage_notes(machine_id),
    })


# === Authenticated Write Endpoints ===

@machine_passport_bp.route('', methods=['POST'])
def create_passport():
    """
    Create a new machine passport.
    
    Requires admin authentication.
    
    Request Body:
    {
        "machine_id": "abc123...",  # Optional: auto-computed if not provided
        "name": "Old Faithful",
        "owner_miner_id": "miner_abc",
        "manufacture_year": 1999,
        "architecture": "PowerPC G4",
        "photo_url": "https://...",
        "provenance": "eBay lot #12345"
    }
    """
    # Admin authentication
    admin_key = request.headers.get('X-Admin-Key', '') or request.headers.get('X-API-Key', '')
    expected_admin_key = os.environ.get('ADMIN_KEY', '')
    
    if expected_admin_key and not hmac.compare_digest(admin_key, expected_admin_key):
        return jsonify({
            'ok': False,
            'error': 'unauthorized',
            'message': 'Admin key required',
        }), 401
    
    data = request.get_json()
    if not data:
        return jsonify({
            'ok': False,
            'error': 'invalid_request',
            'message': 'JSON body required',
        }), 400
    
    # Validate required fields
    required = ['name', 'owner_miner_id']
    for field in required:
        if field not in data:
            return jsonify({
                'ok': False,
                'error': 'missing_field',
                'message': f"Field '{field}' is required",
            }), 400
    
    # Compute machine_id if not provided
    machine_id = data.get('machine_id')
    if not machine_id:
        # Compute from hardware fingerprint if available
        fingerprint = data.get('hardware_fingerprint', {})
        machine_id = compute_machine_id(fingerprint) if fingerprint else None
        
        if not machine_id:
            return jsonify({
                'ok': False,
                'error': 'missing_field',
                'message': "Field 'machine_id' is required or provide 'hardware_fingerprint'",
            }), 400
    
    ledger = get_ledger()
    
    # Check if passport already exists
    existing = ledger.get_passport(machine_id)
    if existing:
        return jsonify({
            'ok': False,
            'error': 'already_exists',
            'message': f'Passport already exists for machine {machine_id}',
        }), 409
    
    passport = MachinePassport(
        machine_id=machine_id,
        name=data['name'],
        owner_miner_id=data['owner_miner_id'],
        manufacture_year=data.get('manufacture_year'),
        architecture=data.get('architecture'),
        photo_hash=data.get('photo_hash'),
        photo_url=data.get('photo_url'),
        provenance=data.get('provenance'),
    )
    
    success, msg = ledger.create_passport(passport)
    
    if success:
        return jsonify({
            'ok': True,
            'message': msg,
            'machine_id': machine_id,
            'passport_url': f'/passport/{machine_id}',
        }), 201
    else:
        return jsonify({
            'ok': False,
            'error': 'creation_failed',
            'message': msg,
        }), 500


@machine_passport_bp.route('/<machine_id>', methods=['PUT'])
def update_passport(machine_id: str):
    """
    Update a machine passport.

    Requires admin authentication when ADMIN_KEY is configured.
    """
    admin_key = request.headers.get('X-Admin-Key', '') or request.headers.get('X-API-Key', '')
    expected_admin_key = os.environ.get('ADMIN_KEY', '')
    
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    if expected_admin_key and not hmac.compare_digest(admin_key, expected_admin_key):
        return jsonify({
            'ok': False,
            'error': 'unauthorized',
            'message': 'Admin key required',
        }), 401
    
    data = request.get_json()
    if not data:
        return jsonify({
            'ok': False,
            'error': 'invalid_request',
            'message': 'JSON body required',
        }), 400
    
    success, msg = ledger.update_passport(machine_id, data)
    
    if success:
        return jsonify({'ok': True, 'message': msg})
    else:
        return jsonify({
            'ok': False,
            'error': 'update_failed',
            'message': msg,
        }), 500


@machine_passport_bp.route('/<machine_id>/repair-log', methods=['POST'])
def add_repair_entry(machine_id: str):
    """
    Add a repair log entry.
    
    Request Body:
    {
        "repair_date": 1234567890,  # Optional: defaults to now
        "repair_type": "capacitor_replacement",
        "description": "Replaced all electrolytic capacitors on logic board",
        "parts_replaced": "C12, C13, C14, C15",
        "technician": "VintageResto Shop",
        "cost_rtc": 50000000,  # 50 RTC in micro units
        "notes": "Machine now stable at 1.2V"
    }
    """
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404

    auth_error = _require_admin(request)
    if auth_error:
        return auth_error
    
    data = request.get_json()
    if not data or 'repair_type' not in data or 'description' not in data:
        return jsonify({
            'ok': False,
            'error': 'missing_field',
            'message': "Fields 'repair_type' and 'description' are required",
        }), 400
    
    success, msg = ledger.add_repair_entry(
        machine_id=machine_id,
        repair_date=data.get('repair_date', int(time.time())),
        repair_type=data['repair_type'],
        description=data['description'],
        parts_replaced=data.get('parts_replaced'),
        technician=data.get('technician'),
        cost_rtc=data.get('cost_rtc'),
        notes=data.get('notes'),
    )
    
    if success:
        return jsonify({'ok': True, 'message': msg})
    else:
        return jsonify({
            'ok': False,
            'error': 'creation_failed',
            'message': msg,
        }), 500


@machine_passport_bp.route('/<machine_id>/attestations', methods=['POST'])
def add_attestation(machine_id: str):
    """
    Record an attestation event.
    
    Typically called automatically during mining attestation.
    """
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404

    auth_error = _require_admin(request)
    if auth_error:
        return auth_error
    
    data, error = get_optional_json_object()
    if error:
        return error
    
    success, msg = ledger.add_attestation(
        machine_id=machine_id,
        attestation_ts=data.get('attestation_ts', int(time.time())),
        epoch=data.get('epoch'),
        total_epochs=data.get('total_epochs'),
        total_rtc_earned=data.get('total_rtc_earned'),
        benchmark_hash=data.get('benchmark_hash'),
        entropy_score=data.get('entropy_score'),
        hardware_binding=data.get('hardware_binding'),
    )
    
    if success:
        return jsonify({'ok': True, 'message': msg})
    else:
        return jsonify({
            'ok': False,
            'error': 'creation_failed',
            'message': msg,
        }), 500


@machine_passport_bp.route('/<machine_id>/benchmarks', methods=['POST'])
def add_benchmark(machine_id: str):
    """
    Record a benchmark signature.
    
    Request Body:
    {
        "cache_timing_profile": "...",
        "simd_identity": "Altivec",
        "thermal_curve": "...",
        "memory_bandwidth": 3200.5,
        "compute_score": 1250.0,
        "entropy_throughput": 500.0
    }
    """
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404

    auth_error = _require_admin(request)
    if auth_error:
        return auth_error
    
    data, error = get_optional_json_object()
    if error:
        return error
    
    success, msg = ledger.add_benchmark(
        machine_id=machine_id,
        benchmark_ts=data.get('benchmark_ts', int(time.time())),
        cache_timing_profile=data.get('cache_timing_profile'),
        simd_identity=data.get('simd_identity'),
        thermal_curve=data.get('thermal_curve'),
        memory_bandwidth=data.get('memory_bandwidth'),
        compute_score=data.get('compute_score'),
        entropy_throughput=data.get('entropy_throughput'),
    )
    
    if success:
        return jsonify({'ok': True, 'message': msg})
    else:
        return jsonify({
            'ok': False,
            'error': 'creation_failed',
            'message': msg,
        }), 500


@machine_passport_bp.route('/<machine_id>/lineage', methods=['POST'])
def add_lineage_note(machine_id: str):
    """
    Add a lineage note (ownership transfer, acquisition, etc.).
    
    Request Body:
    {
        "event_type": "acquisition|transfer|sale|inheritance",
        "from_owner": "previous_owner_id",
        "to_owner": "new_owner_id",
        "description": "Acquired from eBay seller vintage_computing",
        "tx_hash": "0x..."  # Optional blockchain transaction
    }
    """
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404

    auth_error = _require_admin(request)
    if auth_error:
        return auth_error
    
    data = request.get_json()
    if not data or 'event_type' not in data:
        return jsonify({
            'ok': False,
            'error': 'missing_field',
            'message': "Field 'event_type' is required",
        }), 400
    
    success, msg = ledger.add_lineage_note(
        machine_id=machine_id,
        lineage_ts=data.get('lineage_ts', int(time.time())),
        event_type=data['event_type'],
        from_owner=data.get('from_owner'),
        to_owner=data.get('to_owner'),
        description=data.get('description'),
        tx_hash=data.get('tx_hash'),
    )
    
    if success:
        # Update passport owner if to_owner provided
        if data.get('to_owner'):
            ledger.update_passport(machine_id, {'owner_miner_id': data['to_owner']})
        
        return jsonify({'ok': True, 'message': msg})
    else:
        return jsonify({
            'ok': False,
            'error': 'creation_failed',
            'message': msg,
        }), 500


# === Utility Endpoints ===

@machine_passport_bp.route('/<machine_id>/qr', methods=['GET'])
def generate_qr(machine_id: str):
    """
    Generate a QR code for the machine passport.
    
    Returns PNG image or error if library not available.
    """
    import tempfile
    import base64
    from io import BytesIO
    
    ledger = get_ledger()
    passport = ledger.get_passport(machine_id)
    
    if not passport:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    # Generate QR code
    passport_url = f"{request.host_url.rstrip('/')}passport/{machine_id}"
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        success, msg = generate_qr_code(passport_url, tmp_path)
        
        if not success:
            return jsonify({
                'ok': False,
                'error': 'generation_failed',
                'message': msg,
            }), 500
        
        # Read and return as base64
        with open(tmp_path, 'rb') as f:
            qr_data = base64.b64encode(f.read()).decode()
        
        return jsonify({
            'ok': True,
            'machine_id': machine_id,
            'qr_code': f'data:image/png;base64,{qr_data}',
            'passport_url': passport_url,
        })
    finally:
        import os
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@machine_passport_bp.route('/<machine_id>/pdf', methods=['GET'])
def generate_pdf(machine_id: str):
    """
    Generate a printable PDF passport.
    
    Returns PDF file or error if library not available.
    """
    import tempfile
    
    ledger = get_ledger()
    data = ledger.export_passport_full(machine_id)
    
    if not data:
        return jsonify({'ok': False, 'error': 'passport_not_found'}), 404
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        success, msg = generate_passport_pdf(data, tmp_path)
        
        if not success:
            return jsonify({
                'ok': False,
                'error': 'generation_failed',
                'message': msg,
            }), 500
        
        # Return PDF file
        from flask import send_file
        return send_file(
            tmp_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'{machine_id}_passport.pdf',
        )
    finally:
        import os
        # Delay cleanup - send_file needs the file
        import threading
        threading.Timer(1.0, lambda p: os.path.exists(p) and os.unlink(p), [tmp_path]).start()


@machine_passport_bp.route('/compute-machine-id', methods=['POST'])
def compute_machine_id_endpoint():
    """
    Compute a machine ID from hardware fingerprint data.
    
    Useful for miners to determine their machine ID before registration.
    
    Request Body: Hardware fingerprint data (same as attestation)
    """
    data = request.get_json()
    if not data:
        return jsonify({
            'ok': False,
            'error': 'invalid_request',
            'message': 'JSON body required',
        }), 400
    
    machine_id = compute_machine_id(data)
    
    return jsonify({
        'ok': True,
        'machine_id': machine_id,
        'passport_url': f'/passport/{machine_id}',
    })


def register_machine_passport_routes(app):
    """Register machine passport routes with a Flask app."""
    app.register_blueprint(machine_passport_bp)
    print("[Machine Passport] API routes registered")
