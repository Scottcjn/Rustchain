"""
Boot Chime Proof-of-Iron API Endpoints

Flask-based REST API for acoustic hardware attestation.
Integrates with RustChain node for miner attestation.
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import time
import tempfile
from pathlib import Path
from typing import Dict, Any

# Import Proof-of-Iron components
import sys
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from acoustic_fingerprint import AcousticFingerprint
from boot_chime_capture import BootChimeCapture, AudioCaptureConfig
from proof_of_iron import ProofOfIron, ProofOfIronError, AttestationStatus


app = Flask(__name__)
CORS(app, origins=['http://localhost', 'http://127.0.0.1'])  # Restrict in production

# Configuration
API_HOST = os.getenv('BOOT_CHIME_API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('BOOT_CHIME_API_PORT', '8085'))
DB_PATH = os.getenv('BOOT_CHIME_DB_PATH', 'proof_of_iron.db')
SIMILARITY_THRESHOLD = float(os.getenv('BOOT_CHIME_THRESHOLD', '0.85'))
CHALLENGE_TTL = int(os.getenv('BOOT_CHIME_CHALLENGE_TTL', '300'))

# Initialize Proof-of-Iron system
poi_system = ProofOfIron(
    db_path=DB_PATH,
    similarity_threshold=SIMILARITY_THRESHOLD,
    challenge_ttl=CHALLENGE_TTL
)

# Audio capture config
capture_config = AudioCaptureConfig(
    sample_rate=int(os.getenv('AUDIO_SAMPLE_RATE', '44100')),
    duration=float(os.getenv('AUDIO_CAPTURE_DURATION', '5.0')),
    trigger_threshold=float(os.getenv('AUDIO_TRIGGER_THRESHOLD', '0.01'))
)

audio_capture = BootChimeCapture(config=capture_config)
fingerprint_extractor = AcousticFingerprint()


# ============= Health & Info =============

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'boot-chime-proof-of-iron',
        'version': '1.0.0',
        'timestamp': int(time.time())
    })


@app.route('/api/v1/info', methods=['GET'])
def get_info():
    """Get service information"""
    return jsonify({
        'name': 'Boot Chime Proof-of-Iron',
        'version': '1.0.0',
        'description': 'Acoustic hardware attestation for RustChain miners',
        'endpoints': {
            'challenge': '/api/v1/challenge',
            'submit': '/api/v1/submit',
            'verify': '/api/v1/verify',
            'enroll': '/api/v1/enroll',
            'capture': '/api/v1/capture',
            'revoke': '/api/v1/revoke',
            'status': '/api/v1/status/<miner_id>',
            'identity': '/api/v1/identity/<miner_id>'
        }
    })


# ============= Attestation Flow =============

@app.route('/api/v1/challenge', methods=['POST'])
def issue_challenge():
    """
    Issue attestation challenge to miner.
    
    Request:
        { "miner_id": "miner_abc123" }
    
    Response:
        {
            "challenge_id": "...",
            "nonce": "...",
            "expires_at": 1234567890
        }
    """
    try:
        data = request.get_json() or {}
        miner_id = data.get('miner_id')
        
        if not miner_id:
            return jsonify({'error': 'miner_id required'}), 400
        
        challenge = poi_system.issue_challenge(miner_id)
        
        return jsonify({
            'challenge_id': challenge.challenge_id,
            'nonce': challenge.nonce,
            'issued_at': challenge.issued_at,
            'expires_at': challenge.expires_at,
            'ttl_seconds': challenge.expires_at - challenge.issued_at
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/submit', methods=['POST'])
def submit_proof():
    """
    Submit attestation proof.
    
    Request (multipart/form-data):
        - miner_id: string
        - challenge_id: string
        - timestamp: integer
        - audio_signature: string
        - features_hash: string
        - audio: file (WAV)
    
    Response:
        {
            "status": "verified",
            "miner_id": "...",
            "device_id": "...",
            "confidence": 0.95,
            "ttl_seconds": 86400
        }
    """
    try:
        miner_id = request.form.get('miner_id')
        challenge_id = request.form.get('challenge_id')
        timestamp = request.form.get('timestamp', type=int)
        audio_signature = request.form.get('audio_signature')
        features_hash = request.form.get('features_hash')
        
        if not all([miner_id, challenge_id, timestamp]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Load audio file if provided
        audio_data = None
        if 'audio' in request.files:
            audio_file = request.files['audio']
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                audio_file.save(tmp)
                tmp_path = tmp.name
            
            try:
                captured = audio_capture.capture_from_file(tmp_path)
                audio_data = captured.data
            finally:
                os.unlink(tmp_path)
        
        # Create proof object
        from proof_of_iron import AttestationProof
        
        proof = AttestationProof(
            challenge_id=challenge_id,
            miner_id=miner_id,
            audio_signature=audio_signature or "",
            features_hash=features_hash or "",
            timestamp=timestamp,
            proof_data={'valid': True}
        )
        
        result = poi_system.submit_proof(proof, audio_data)
        
        status_code = 200 if result.status == AttestationStatus.VERIFIED else 400
        
        return jsonify(result.to_dict()), status_code
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/verify/<miner_id>', methods=['GET'])
def verify_miner(miner_id: str):
    """
    Verify miner attestation status.
    
    Response:
        {
            "status": "verified",
            "miner_id": "...",
            "confidence": 0.95,
            "verified_at": 1234567890,
            "expires_at": 1234654290
        }
    """
    try:
        result = poi_system.verify_miner(miner_id)
        return jsonify(result.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/enroll', methods=['POST'])
def enroll_miner():
    """
    Enroll new miner with boot chime capture.
    
    Request (multipart/form-data):
        - miner_id: string
        - audio: file (WAV, optional)
    
    Response:
        {
            "status": "verified",
            "device_id": "...",
            "acoustic_signature": "...",
            "confidence": 0.92
        }
    """
    try:
        miner_id = request.form.get('miner_id')
        
        if not miner_id:
            return jsonify({'error': 'miner_id required'}), 400
        
        # Check if audio file provided
        audio_file = None
        if 'audio' in request.files:
            audio = request.files['audio']
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                audio.save(tmp)
                audio_file = tmp.name
        
        result = poi_system.capture_and_enroll(miner_id, audio_file)
        
        status_code = 200 if result.status == AttestationStatus.VERIFIED else 400
        
        return jsonify(result.to_dict()), status_code
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/capture', methods=['POST'])
def capture_audio():
    """
    Capture boot chime audio (for testing).
    
    Query params:
        - duration: float (seconds)
        - trigger: bool (wait for trigger)
    
    Response: WAV file
    """
    try:
        duration = request.args.get('duration', default=5.0, type=float)
        trigger = request.args.get('trigger', default='false').lower() == 'true'
        
        captured = audio_capture.capture(duration=duration, trigger=trigger)
        
        # Save to temp file and return
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            audio_capture.save_audio(captured, tmp.name)
            tmp_path = tmp.name
        
        return send_file(
            tmp_path,
            mimetype='audio/wav',
            as_attachment=True,
            download_name=f'boot_chime_{int(time.time())}.wav'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/revoke', methods=['POST'])
def revoke_attestation():
    """
    Revoke miner attestation.
    
    Request:
        {
            "miner_id": "...",
            "reason": "..." (optional)
        }
    
    Response:
        { "success": true, "message": "..." }
    """
    try:
        data = request.get_json() or {}
        miner_id = data.get('miner_id')
        reason = data.get('reason', '')
        
        if not miner_id:
            return jsonify({'error': 'miner_id required'}), 400
        
        success = poi_system.revoke_attestation(miner_id, reason)
        
        if success:
            return jsonify({'success': True, 'message': 'Attestation revoked'})
        else:
            return jsonify({'error': 'Miner not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/status/<miner_id>', methods=['GET'])
def get_status(miner_id: str):
    """Get detailed attestation status for miner"""
    try:
        result = poi_system.verify_miner(miner_id)
        identity = poi_system.get_hardware_identity(miner_id)
        history = poi_system.get_attestation_history(miner_id)
        
        response = {
            'miner_id': miner_id,
            'current_status': result.to_dict(),
            'identity': identity.to_dict() if identity else None,
            'history': [h.to_dict() for h in history]
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/identity/<miner_id>', methods=['GET'])
def get_identity(miner_id: str):
    """Get hardware identity for miner"""
    try:
        identity = poi_system.get_hardware_identity(miner_id)
        
        if identity:
            return jsonify(identity.to_dict())
        else:
            return jsonify({'error': 'Identity not found'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= Analytics & Metrics =============

@app.route('/api/v1/metrics', methods=['GET'])
def get_metrics():
    """Get attestation system metrics"""
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Count attestations by status
        c.execute('SELECT status, COUNT(*) FROM attestations GROUP BY status')
        status_counts = dict(c.fetchall())
        
        # Total identities
        c.execute('SELECT COUNT(*) FROM identities')
        total_identities = c.fetchone()[0]
        
        # Recent attestations (last 24h)
        now = int(time.time())
        day_ago = now - 86400
        c.execute('SELECT COUNT(*) FROM attestations WHERE verified_at > ?', (day_ago,))
        recent_attestations = c.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_identities': total_identities,
            'attestations_by_status': status_counts,
            'attestations_last_24h': recent_attestations,
            'similarity_threshold': SIMILARITY_THRESHOLD,
            'challenge_ttl': CHALLENGE_TTL
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/analyze', methods=['POST'])
def analyze_audio():
    """
    Analyze uploaded audio file.
    
    Request (multipart/form-data):
        - audio: file (WAV)
    
    Response:
        {
            "features": {...},
            "signature": "...",
            "is_boot_chime": true,
            "detection_confidence": 0.87
        }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'audio file required'}), 400
        
        audio_file = request.files['audio']
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
            audio_file.save(tmp)
            tmp_path = tmp.name
        
        try:
            captured = audio_capture.capture_from_file(tmp_path)
            
            # Extract features
            features = fingerprint_extractor.extract(captured.data)
            signature = fingerprint_extractor.compute_signature(features)
            
            # Detect if boot chime
            is_boot_chime, detection = audio_capture.detect_boot_chime(captured)
            
            return jsonify({
                'features': {
                    'mfcc_mean': features.mfcc_mean.tolist(),
                    'mfcc_std': features.mfcc_std.tolist(),
                    'spectral_centroid': features.spectral_centroid,
                    'spectral_bandwidth': features.spectral_bandwidth,
                    'zero_crossing_rate': features.zero_crossing_rate,
                },
                'signature': signature,
                'is_boot_chime': is_boot_chime,
                'detection': detection,
                'quality_score': captured.quality_score,
                'duration': captured.duration
            })
            
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============= Error Handlers =============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ============= Main =============

if __name__ == '__main__':
    print(f"Starting Boot Chime Proof-of-Iron API...")
    print(f"  Host: {API_HOST}")
    print(f"  Port: {API_PORT}")
    print(f"  DB: {DB_PATH}")
    print(f"  Threshold: {SIMILARITY_THRESHOLD}")
    print()
    print("Endpoints:")
    print("  POST /api/v1/challenge  - Issue attestation challenge")
    print("  POST /api/v1/submit     - Submit attestation proof")
    print("  GET  /api/v1/verify/:id - Verify miner attestation")
    print("  POST /api/v1/enroll     - Enroll new miner")
    print("  POST /api/v1/capture    - Capture boot chime audio")
    print("  POST /api/v1/revoke     - Revoke attestation")
    print("  GET  /api/v1/status/:id - Get miner status")
    print("  GET  /api/v1/identity/:id - Get hardware identity")
    print("  GET  /api/v1/metrics    - Get system metrics")
    print("  POST /api/v1/analyze    - Analyze audio file")
    print()
    
    app.run(host=API_HOST, port=API_PORT, debug=False)
