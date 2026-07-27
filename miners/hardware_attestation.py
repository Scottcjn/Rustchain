import json
from typing import Dict, Any
from fingerprint_checks import get_fingerprint, generate_fingerprint_hash

class HardwareAttestation:
    """Class to handle hardware attestation and fingerprint storage."""

    def __init__(self):
        self.fingerprint = None
        self.fingerprint_hash = None

    def generate_attestation(self) -> Dict[str, Any]:
        """Generate hardware attestation data."""
        self.fingerprint = get_fingerprint()
        self.fingerprint_hash = generate_fingerprint_hash(self.fingerprint)

        attestation = {
            'fingerprint': self.fingerprint,
            'fingerprint_hash': self.fingerprint_hash,
            'timestamp': datetime.datetime.now().isoformat()
        }

        return attestation

    def save_attestation(self, filename: str) -> None:
        """Save attestation data to a file."""
        if not self.fingerprint or not self.fingerprint_hash:
            self.generate_attestation()

        with open(filename, 'w') as f:
            json.dump({
                'fingerprint': self.fingerprint,
                'fingerprint_hash': self.fingerprint_hash
            }, f, indent=4)

    def load_attestation(self, filename: str) -> Dict[str, Any]:
        """Load attestation data from a file."""
        with open(filename, 'r') as f:
            data = json.load(f)
            self.fingerprint = data['fingerprint']
            self.fingerprint_hash = data['fingerprint_hash']
            return data

if __name__ == '__main__':
    attestation = HardwareAttestation()
    attestation_data = attestation.generate_attestation()
    print("Hardware Attestation:")
    print(json.dumps(attestation_data, indent=4))
    attestation.save_attestation('hardware_attestation.json')