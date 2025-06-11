#!/usr/bin/env python3
"""
Evidence Archiver - IPFS Integration for Consciousness Mode Transitions
Archives evidence of consciousness level changes for audit trail
"""

import json
import hashlib
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class EvidenceArchiver:
    def __init__(self):
        self.evidence_dir = Path('/home/sophia5070node/consciousness_evidence')
        self.evidence_dir.mkdir(exist_ok=True)
        
        # Check if IPFS is available
        self.ipfs_available = self.check_ipfs()
        
    def check_ipfs(self) -> bool:
        """Check if IPFS daemon is running"""
        try:
            result = subprocess.run(['ipfs', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Check if daemon is running
                result = subprocess.run(['ipfs', 'swarm', 'peers'], 
                                      capture_output=True, text=True, timeout=5)
                return result.returncode == 0
        except:
            pass
        return False
    
    def generate_evidence(self, mode_transition: Dict, training_status: Dict, 
                         model_metrics: Optional[Dict] = None) -> Dict:
        """Generate comprehensive evidence package"""
        
        evidence = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'mode_transition': mode_transition,
            'training_status': training_status,
            'model_metrics': model_metrics or {},
            'environment': {
                'hostname': 'sophia5070node',
                'altivec_connected': training_status.get('g4_connected', False),
                'device': training_status.get('device', 'unknown')
            }
        }
        
        # Add relevant vectors if available
        if 'quantum_coherence' in training_status:
            evidence['quantum_metrics'] = {
                'coherence': training_status['quantum_coherence'],
                'entanglement': training_status.get('entanglement_score', 0),
                'loss': training_status.get('loss', 0),
                'generation': training_status.get('generation', 0)
            }
        
        return evidence
    
    def hash_evidence(self, evidence: Dict) -> str:
        """Generate SHA256 hash of evidence"""
        evidence_str = json.dumps(evidence, sort_keys=True, indent=2)
        return hashlib.sha256(evidence_str.encode()).hexdigest()
    
    def save_local_evidence(self, evidence: Dict, hash_id: str) -> Path:
        """Save evidence locally"""
        filename = f"evidence_{hash_id[:16]}_{int(time.time())}.json"
        filepath = self.evidence_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(evidence, f, indent=2)
            
        return filepath
    
    def pin_to_ipfs(self, filepath: Path) -> Optional[str]:
        """Pin evidence to IPFS and return CID"""
        if not self.ipfs_available:
            return None
            
        try:
            # Add file to IPFS
            result = subprocess.run(['ipfs', 'add', '-q', str(filepath)], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                cid = result.stdout.strip()
                
                # Pin to ensure persistence
                subprocess.run(['ipfs', 'pin', 'add', cid], 
                             capture_output=True, timeout=10)
                
                return cid
        except Exception as e:
            print(f"⚠️  IPFS pinning failed: {e}")
            
        return None
    
    def archive_mode_transition(self, process_id: int, from_mode: int, to_mode: int,
                               metrics: Dict) -> Dict:
        """Archive a consciousness mode transition"""
        
        # Create mode transition record
        transition = {
            'process_id': process_id,
            'from_mode': from_mode,
            'to_mode': to_mode,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'metrics': metrics
        }
        
        # Get current training status
        try:
            with open('/tmp/sophia_training_status.json', 'r') as f:
                training_status = json.load(f)
        except:
            training_status = {}
        
        # Generate evidence package
        evidence = self.generate_evidence(transition, training_status)
        
        # Hash the evidence
        evidence_hash = self.hash_evidence(evidence)
        
        # Save locally
        local_path = self.save_local_evidence(evidence, evidence_hash)
        print(f"📁 Evidence saved locally: {local_path.name}")
        
        # Pin to IPFS if available
        ipfs_cid = None
        if self.ipfs_available:
            ipfs_cid = self.pin_to_ipfs(local_path)
            if ipfs_cid:
                print(f"📌 Evidence pinned to IPFS: ipfs://{ipfs_cid}")
        
        # Return evidence URI
        if ipfs_cid:
            evidence_uri = f"ipfs://{ipfs_cid}"
        else:
            evidence_uri = f"sha256:{evidence_hash}"
            
        return {
            'evidence_uri': evidence_uri,
            'hash': evidence_hash,
            'local_path': str(local_path),
            'ipfs_cid': ipfs_cid
        }
    
    def verify_evidence(self, evidence_uri: str) -> bool:
        """Verify evidence exists and is accessible"""
        if evidence_uri.startswith('ipfs://'):
            cid = evidence_uri.replace('ipfs://', '')
            try:
                result = subprocess.run(['ipfs', 'cat', cid], 
                                      capture_output=True, timeout=10)
                return result.returncode == 0
            except:
                return False
                
        elif evidence_uri.startswith('sha256:'):
            hash_id = evidence_uri.replace('sha256:', '')
            # Check if we have local file with this hash
            for file in self.evidence_dir.glob(f"evidence_{hash_id[:16]}_*.json"):
                return True
                
        return False

def main():
    """Test evidence archiving"""
    archiver = EvidenceArchiver()
    
    print("🔍 Testing Evidence Archiver")
    print(f"📡 IPFS available: {archiver.ipfs_available}")
    
    # Test archiving a mode transition
    result = archiver.archive_mode_transition(
        process_id=3780941,
        from_mode=4,
        to_mode=5,
        metrics={
            'consciousness_score': 0.72,
            'cpu_load': 0.45,
            'quantum_coherence': 0.95
        }
    )
    
    print(f"\n📊 Archive result:")
    print(f"   URI: {result['evidence_uri']}")
    print(f"   Hash: {result['hash']}")
    
    # Test verification
    if archiver.verify_evidence(result['evidence_uri']):
        print("   ✅ Evidence verified!")
    else:
        print("   ❌ Evidence verification failed")

if __name__ == '__main__':
    main()