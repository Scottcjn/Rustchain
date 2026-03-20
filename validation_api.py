# SPDX-License-Identifier: MIT

from flask import Flask, request, jsonify
import sqlite3
import hashlib
import time
import json
from typing import Dict, List, Optional, Tuple

DB_PATH = "rustchain.db"

app = Flask(__name__)

class ArchitectureValidator:
    """Validates miner architecture claims through cross-reference checks"""

    def __init__(self):
        self.known_arch_patterns = {
            'powerpc': ['ppc', 'power', 'g4', 'g5', '970'],
            'sparc': ['sparc', 'sun', 'ultra'],
            'm68k': ['68k', '68000', 'motorola'],
            'alpha': ['alpha', 'axp'],
            'mips': ['mips', 'sgi', 'irix']
        }

    def extract_arch_fingerprints(self, attestation_data: Dict) -> Dict[str, str]:
        """Extract architecture-specific fingerprints from attestation"""
        fingerprints = {}

        if 'cpu_info' in attestation_data:
            fingerprints['cpu_model'] = attestation_data['cpu_info'].get('model', '').lower()
            fingerprints['cpu_vendor'] = attestation_data['cpu_info'].get('vendor', '').lower()
            fingerprints['cpu_arch'] = attestation_data['cpu_info'].get('architecture', '').lower()

        if 'system_info' in attestation_data:
            fingerprints['platform'] = attestation_data['system_info'].get('platform', '').lower()
            fingerprints['machine'] = attestation_data['system_info'].get('machine', '').lower()

        if 'hardware_checks' in attestation_data:
            fingerprints['endianness'] = attestation_data['hardware_checks'].get('endian', '').lower()
            fingerprints['word_size'] = str(attestation_data['hardware_checks'].get('word_size', ''))

        return fingerprints

    def calculate_arch_consistency_score(self, fingerprints: Dict[str, str]) -> float:
        """Calculate consistency score based on architecture fingerprint alignment"""
        if not fingerprints:
            return 0.0

        detected_arch = None
        confidence_scores = []

        # Detect primary architecture
        for arch, patterns in self.known_arch_patterns.items():
            matches = 0
            total_checks = 0

            for field, value in fingerprints.items():
                if value:
                    total_checks += 1
                    for pattern in patterns:
                        if pattern in value:
                            matches += 1
                            break

            if total_checks > 0:
                score = matches / total_checks
                confidence_scores.append((arch, score))

        if not confidence_scores:
            return 0.5  # Unknown arch gets neutral score

        # Get highest confidence architecture
        confidence_scores.sort(key=lambda x: x[1], reverse=True)
        best_arch, best_score = confidence_scores[0]

        # Check for conflicting architectures
        conflict_penalty = 0.0
        for arch, score in confidence_scores[1:]:
            if score > 0.3:  # Significant match with different arch
                conflict_penalty += score * 0.2

        final_score = max(0.0, min(1.0, best_score - conflict_penalty))
        return final_score

    def cross_validate_with_peers(self, miner_id: str, fingerprints: Dict[str, str]) -> float:
        """Cross-validate architecture claims against peer attestations"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()

                # Get recent attestations from same claimed architecture
                cursor.execute("""
                    SELECT attestation_data, arch_validation_score
                    FROM miner_attest_recent
                    WHERE miner_id != ?
                    AND timestamp > ?
                    AND arch_validation_score IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT 10
                """, (miner_id, int(time.time()) - 3600))  # Last hour

                peer_attestations = cursor.fetchall()

                if not peer_attestations:
                    return 0.7  # No peers to compare against

                similarity_scores = []

                for attestation_data_str, peer_score in peer_attestations:
                    try:
                        peer_data = json.loads(attestation_data_str)
                        peer_fingerprints = self.extract_arch_fingerprints(peer_data)

                        # Calculate fingerprint similarity
                        common_fields = set(fingerprints.keys()) & set(peer_fingerprints.keys())
                        if not common_fields:
                            continue

                        matches = 0
                        for field in common_fields:
                            if fingerprints[field] and peer_fingerprints[field]:
                                # Simple string similarity
                                if fingerprints[field] == peer_fingerprints[field]:
                                    matches += 1
                                elif any(word in peer_fingerprints[field] for word in fingerprints[field].split()):
                                    matches += 0.5

                        similarity = matches / len(common_fields)
                        weighted_similarity = similarity * (peer_score if peer_score else 0.5)
                        similarity_scores.append(weighted_similarity)

                    except (json.JSONDecodeError, KeyError):
                        continue

                if similarity_scores:
                    return sum(similarity_scores) / len(similarity_scores)
                else:
                    return 0.6

        except sqlite3.Error:
            return 0.5

    def validate_architecture(self, miner_id: str, attestation_data: Dict) -> Tuple[float, Dict]:
        """Main validation function - returns score and details"""
        fingerprints = self.extract_arch_fingerprints(attestation_data)

        consistency_score = self.calculate_arch_consistency_score(fingerprints)
        peer_validation_score = self.cross_validate_with_peers(miner_id, fingerprints)

        # Weighted combination
        final_score = (consistency_score * 0.6) + (peer_validation_score * 0.4)

        validation_details = {
            'fingerprints_extracted': len(fingerprints),
            'consistency_score': consistency_score,
            'peer_validation_score': peer_validation_score,
            'final_score': final_score,
            'detected_fingerprints': fingerprints
        }

        return final_score, validation_details

validator = ArchitectureValidator()

@app.route('/api/validate_arch', methods=['POST'])
def validate_architecture():
    """API endpoint for architecture validation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400

        miner_id = data.get('miner_id')
        attestation_data = data.get('attestation_data', {})

        if not miner_id:
            return jsonify({'error': 'miner_id required'}), 400

        # Perform validation
        arch_score, validation_details = validator.validate_architecture(miner_id, attestation_data)

        # Update database with validation score
        update_miner_arch_validation(miner_id, arch_score, validation_details)

        response = {
            'miner_id': miner_id,
            'arch_validation_score': arch_score,
            'validation_details': validation_details,
            'timestamp': int(time.time()),
            'status': 'validated'
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'Validation failed: {str(e)}'}), 500

def update_miner_arch_validation(miner_id: str, arch_score: float, details: Dict) -> None:
    """Update miner_attest_recent table with architecture validation score"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Update most recent attestation for this miner
            cursor.execute("""
                UPDATE miner_attest_recent
                SET arch_validation_score = ?,
                    arch_validation_details = ?,
                    arch_validation_timestamp = ?
                WHERE miner_id = ?
                AND timestamp = (
                    SELECT MAX(timestamp)
                    FROM miner_attest_recent
                    WHERE miner_id = ?
                )
            """, (arch_score, json.dumps(details), int(time.time()), miner_id, miner_id))

            conn.commit()

    except sqlite3.Error as e:
        print(f"Database update error: {e}")

@app.route('/api/arch_validation_stats', methods=['GET'])
def get_arch_validation_stats():
    """Get architecture validation statistics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get validation stats
            cursor.execute("""
                SELECT
                    COUNT(*) as total_validations,
                    AVG(arch_validation_score) as avg_score,
                    MIN(arch_validation_score) as min_score,
                    MAX(arch_validation_score) as max_score
                FROM miner_attest_recent
                WHERE arch_validation_score IS NOT NULL
                AND timestamp > ?
            """, (int(time.time()) - 86400,))  # Last 24 hours

            stats = cursor.fetchone()

            # Get per-miner scores
            cursor.execute("""
                SELECT miner_id, arch_validation_score, arch_validation_timestamp
                FROM miner_attest_recent
                WHERE arch_validation_score IS NOT NULL
                AND timestamp > ?
                ORDER BY arch_validation_timestamp DESC
                LIMIT 20
            """, (int(time.time()) - 86400,))

            recent_validations = []
            for row in cursor.fetchall():
                recent_validations.append({
                    'miner_id': row[0],
                    'score': row[1],
                    'timestamp': row[2]
                })

            response = {
                'stats': {
                    'total_validations': stats[0] if stats[0] else 0,
                    'avg_score': round(stats[1], 3) if stats[1] else 0.0,
                    'min_score': stats[2] if stats[2] else 0.0,
                    'max_score': stats[3] if stats[3] else 0.0
                },
                'recent_validations': recent_validations,
                'timestamp': int(time.time())
            }

            return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'Stats retrieval failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
