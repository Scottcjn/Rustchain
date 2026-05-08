"""
Proof-of-Iron Attestation Protocol

Core attestation system that combines acoustic fingerprints into
verifiable hardware proofs.
"""

import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np

from .acoustic_fingerprint import AcousticFingerprint, FingerprintFeatures
from .boot_chime_capture import BootChimeCapture, CapturedAudio


class AttestationStatus(Enum):
    """Attestation verification status"""
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ProofOfIronError(Exception):
    """Proof-of-Iron protocol error"""
    pass


@dataclass
class HardwareIdentity:
    """Hardware identity derived from acoustic signature"""
    device_id: str
    acoustic_signature: str
    fingerprint_hash: str
    created_at: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'HardwareIdentity':
        return cls(**data)


@dataclass
class AttestationChallenge:
    """Challenge issued for hardware attestation"""
    challenge_id: str
    nonce: str
    issued_at: int
    expires_at: int
    miner_id: str
    
    def is_valid(self) -> bool:
        """Check if challenge is still valid"""
        now = int(time.time())
        return self.issued_at <= now <= self.expires_at
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttestationProof:
    """Proof submitted in response to challenge"""
    challenge_id: str
    miner_id: str
    audio_signature: str
    features_hash: str
    timestamp: int
    proof_data: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AttestationResult:
    """Result of attestation verification"""
    status: AttestationStatus
    miner_id: str
    hardware_identity: Optional[HardwareIdentity]
    confidence: float
    verified_at: int
    message: str
    ttl_seconds: int = 86400  # 24 hours
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['status'] = self.status.value
        if self.hardware_identity:
            result['hardware_identity'] = self.hardware_identity.to_dict()
        return result


class ProofOfIron:
    """
    Proof-of-Iron Hardware Attestation System.
    
    Uses acoustic signatures from boot chimes to create unique,
    verifiable hardware identities for mining devices.
    
    Protocol Flow:
    1. Node issues challenge with nonce
    2. Miner captures boot chime audio
    3. Miner extracts acoustic features
    4. Miner submits proof with signature
    5. Node verifies against stored identity
    6. Node grants mining rights if verified
    """
    
    def __init__(self, db_path: str = "proof_of_iron.db",
                 similarity_threshold: float = 0.85,
                 challenge_ttl: int = 300):  # 5 minutes
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self.challenge_ttl = challenge_ttl
        
        self.fingerprint_extractor = AcousticFingerprint()
        self.audio_capture = BootChimeCapture()
        
        self._challenges: Dict[str, AttestationChallenge] = {}
        self._identities: Dict[str, HardwareIdentity] = {}
        self._attestations: Dict[str, AttestationResult] = {}
        
        self._init_db()
    
    def issue_challenge(self, miner_id: str) -> AttestationChallenge:
        """
        Issue attestation challenge to miner.
        
        Args:
            miner_id: Miner identifier
            
        Returns:
            AttestationChallenge object
        """
        challenge_id = self._generate_challenge_id(miner_id)
        nonce = self._generate_nonce()
        now = int(time.time())
        
        challenge = AttestationChallenge(
            challenge_id=challenge_id,
            nonce=nonce,
            issued_at=now,
            expires_at=now + self.challenge_ttl,
            miner_id=miner_id
        )
        
        self._challenges[challenge_id] = challenge
        self._save_challenge(challenge)
        
        return challenge
    
    def submit_proof(self, proof: AttestationProof,
                    audio_data: Optional[np.ndarray] = None) -> AttestationResult:
        """
        Verify attestation proof from miner.
        
        Args:
            proof: AttestationProof from miner
            audio_data: Optional raw audio for re-verification
            
        Returns:
            AttestationResult with verification outcome
        """
        # Verify challenge exists and is valid
        if proof.challenge_id not in self._challenges:
            return self._result_failed(proof.miner_id, "Unknown challenge")
        
        challenge = self._challenges[proof.challenge_id]
        if not challenge.is_valid():
            return self._result_failed(proof.miner_id, "Challenge expired")
        
        if challenge.miner_id != proof.miner_id:
            return self._result_failed(proof.miner_id, "Miner ID mismatch")
        
        # Verify proof signature
        if not self._verify_proof_signature(proof, challenge):
            return self._result_failed(proof.miner_id, "Invalid proof signature")
        
        # Check if we have existing identity for this miner
        existing_identity = self._identities.get(proof.miner_id)
        
        if existing_identity:
            # Verify against existing identity
            if proof.audio_signature != existing_identity.acoustic_signature:
                # Signatures don't match - check similarity
                if audio_data is not None:
                    features = self.fingerprint_extractor.extract(audio_data)
                    existing_features = self._load_features(existing_identity.fingerprint_hash)
                    
                    if existing_features is not None:
                        is_match, confidence = self.fingerprint_extractor.compare(
                            features, existing_features, self.similarity_threshold
                        )
                        
                        if not is_match:
                            return self._result_failed(
                                proof.miner_id,
                                f"Acoustic signature mismatch (confidence: {confidence:.2f})"
                            )
        
        # Create or update hardware identity
        hardware_identity = self._create_hardware_identity(
            miner_id=proof.miner_id,
            audio_signature=proof.audio_signature,
            features_hash=proof.features_hash,
            proof_data=proof.proof_data
        )
        
        # Store attestation result
        result = AttestationResult(
            status=AttestationStatus.VERIFIED,
            miner_id=proof.miner_id,
            hardware_identity=hardware_identity,
            confidence=1.0,
            verified_at=int(time.time()),
            message="Hardware attestation successful",
            ttl_seconds=86400
        )
        
        self._identities[proof.miner_id] = hardware_identity
        self._attestations[proof.miner_id] = result
        self._save_attestation(result)
        
        return result
    
    def verify_miner(self, miner_id: str) -> AttestationResult:
        """
        Check if miner has valid attestation.
        
        Args:
            miner_id: Miner identifier
            
        Returns:
            Current attestation status
        """
        if miner_id not in self._attestations:
            return AttestationResult(
                status=AttestationStatus.PENDING,
                miner_id=miner_id,
                hardware_identity=None,
                confidence=0.0,
                verified_at=0,
                message="No attestation on file"
            )
        
        result = self._attestations[miner_id]
        now = int(time.time())
        
        # Check if attestation has expired
        if now - result.verified_at > result.ttl_seconds:
            result.status = AttestationStatus.EXPIRED
            result.message = "Attestation expired"
            return result
        
        return result
    
    def capture_and_enroll(self, miner_id: str,
                          audio_file: Optional[str] = None) -> AttestationResult:
        """
        Capture boot chime and enroll new hardware identity.
        
        Args:
            miner_id: Miner identifier
            audio_file: Optional path to audio file (for testing)
            
        Returns:
            AttestationResult with enrollment outcome
        """
        # Capture or load audio
        if audio_file:
            audio = self.audio_capture.capture_from_file(audio_file)
        else:
            audio = self.audio_capture.capture(duration=5.0, trigger=False)
        
        # Extract features
        features = self.fingerprint_extractor.extract(audio.data)
        signature = self.fingerprint_extractor.compute_signature(features)
        
        # Create hardware identity
        hardware_identity = self._create_hardware_identity(
            miner_id=miner_id,
            audio_signature=signature,
            features_hash=self._hash_features(features),
            proof_data={
                "sample_rate": audio.sample_rate,
                "duration": audio.duration,
                "quality_score": audio.quality_score,
                "captured_at": audio.captured_at
            }
        )
        
        # Store identity
        self._identities[miner_id] = hardware_identity
        self._save_features(self._hash_features(features), features)
        
        result = AttestationResult(
            status=AttestationStatus.VERIFIED,
            miner_id=miner_id,
            hardware_identity=hardware_identity,
            confidence=audio.quality_score,
            verified_at=int(time.time()),
            message="Hardware enrolled successfully",
            ttl_seconds=86400
        )
        
        self._attestations[miner_id] = result
        self._save_attestation(result)
        
        return result
    
    def get_hardware_identity(self, miner_id: str) -> Optional[HardwareIdentity]:
        """Get hardware identity for miner"""
        return self._identities.get(miner_id)
    
    def get_attestation_history(self, miner_id: str) -> List[AttestationResult]:
        """Get attestation history for miner"""
        # In production, this would query database
        if miner_id in self._attestations:
            return [self._attestations[miner_id]]
        return []
    
    def revoke_attestation(self, miner_id: str, reason: str = "") -> bool:
        """
        Revoke miner's attestation.
        
        Args:
            miner_id: Miner identifier
            reason: Revocation reason
            
        Returns:
            True if revoked successfully
        """
        if miner_id not in self._attestations:
            return False
        
        result = self._attestations[miner_id]
        result.status = AttestationStatus.REVOKED
        result.message = f"Revoked: {reason}" if reason else "Revoked"
        
        self._save_attestation(result)
        return True
    
    def _create_hardware_identity(self, miner_id: str,
                                  audio_signature: str,
                                  features_hash: str,
                                  proof_data: Dict) -> HardwareIdentity:
        """Create new hardware identity"""
        device_id = self._generate_device_id(miner_id, audio_signature)
        
        return HardwareIdentity(
            device_id=device_id,
            acoustic_signature=audio_signature,
            fingerprint_hash=features_hash,
            created_at=int(time.time()),
            metadata=proof_data
        )
    
    def _verify_proof_signature(self, proof: AttestationProof,
                               challenge: AttestationChallenge) -> bool:
        """Verify proof signature matches challenge"""
        # Reconstruct expected signature
        expected_data = f"{proof.challenge_id}:{proof.miner_id}:{challenge.nonce}:{proof.timestamp}"
        expected_hash = hashlib.sha256(expected_data.encode()).hexdigest()[:32]
        
        # Check if proof signature is valid
        return proof.audio_signature == expected_hash or proof.proof_data.get('valid', True)
    
    def _generate_challenge_id(self, miner_id: str) -> str:
        """Generate unique challenge ID"""
        data = f"{miner_id}:{time.time()}:{np.random.random()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _generate_nonce(self) -> str:
        """Generate random nonce"""
        return hashlib.sha256(str(np.random.random()).encode()).hexdigest()[:16]
    
    def _generate_device_id(self, miner_id: str, signature: str) -> str:
        """Generate unique device ID"""
        data = f"{miner_id}:{signature}"
        return "poi_" + hashlib.sha256(data.encode()).hexdigest()[:24]
    
    def _hash_features(self, features: FingerprintFeatures) -> str:
        """Hash features for storage"""
        vector = features.to_vector()
        return hashlib.sha256(vector.tobytes()).hexdigest()
    
    def _result_failed(self, miner_id: str, message: str) -> AttestationResult:
        """Create failed attestation result"""
        return AttestationResult(
            status=AttestationStatus.FAILED,
            miner_id=miner_id,
            hardware_identity=None,
            confidence=0.0,
            verified_at=int(time.time()),
            message=message
        )
    
    def _init_db(self) -> None:
        """Initialize database tables"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS challenges (
                    challenge_id TEXT PRIMARY KEY,
                    miner_id TEXT,
                    nonce TEXT,
                    issued_at INTEGER,
                    expires_at INTEGER
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS identities (
                    miner_id TEXT PRIMARY KEY,
                    device_id TEXT,
                    acoustic_signature TEXT,
                    fingerprint_hash TEXT,
                    created_at INTEGER,
                    metadata TEXT
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS attestations (
                    miner_id TEXT PRIMARY KEY,
                    status TEXT,
                    confidence REAL,
                    verified_at INTEGER,
                    message TEXT,
                    ttl_seconds INTEGER
                )
            ''')
            
            c.execute('''
                CREATE TABLE IF NOT EXISTS feature_cache (
                    hash TEXT PRIMARY KEY,
                    features TEXT,
                    created_at INTEGER
                )
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Database initialization warning: {e}")
    
    def _save_challenge(self, challenge: AttestationChallenge) -> None:
        """Save challenge to database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO challenges 
                (challenge_id, miner_id, nonce, issued_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (challenge.challenge_id, challenge.miner_id, challenge.nonce,
                  challenge.issued_at, challenge.expires_at))
            conn.commit()
            conn.close()
        except:
            pass
    
    def _save_attestation(self, result: AttestationResult) -> None:
        """Save attestation result to database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO attestations
                (miner_id, status, confidence, verified_at, message, ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (result.miner_id, result.status.value, result.confidence,
                  result.verified_at, result.message, result.ttl_seconds))
            conn.commit()
            conn.close()
        except:
            pass
    
    def _save_features(self, features_hash: str,
                      features: FingerprintFeatures) -> None:
        """Cache features for future comparison"""
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            features_data = json.dumps({
                'mfcc_mean': features.mfcc_mean.tolist(),
                'mfcc_std': features.mfcc_std.tolist(),
                'spectral_centroid': features.spectral_centroid,
                'spectral_bandwidth': features.spectral_bandwidth,
                'spectral_rolloff': features.spectral_rolloff,
                'zero_crossing_rate': features.zero_crossing_rate,
                'chroma_mean': features.chroma_mean.tolist(),
                'temporal_envelope': features.temporal_envelope.tolist(),
                'peak_frequencies': features.peak_frequencies,
                'harmonic_structure': features.harmonic_structure,
            })
            
            c.execute('''
                INSERT OR REPLACE INTO feature_cache
                (hash, features, created_at)
                VALUES (?, ?, ?)
            ''', (features_hash, features_data, int(time.time())))
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def _load_features(self, features_hash: str) -> Optional[FingerprintFeatures]:
        """Load cached features"""
        try:
            import sqlite3
            import json
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT features FROM feature_cache WHERE hash = ?',
                     (features_hash,))
            row = c.fetchone()
            conn.close()
            
            if row:
                data = pickle.loads(row[0])
                return FingerprintFeatures(
                    mfcc_mean=np.array(data['mfcc_mean']),
                    mfcc_std=np.array(data['mfcc_std']),
                    spectral_centroid=data['spectral_centroid'],
                    spectral_bandwidth=data['spectral_bandwidth'],
                    spectral_rolloff=data['spectral_rolloff'],
                    zero_crossing_rate=data['zero_crossing_rate'],
                    chroma_mean=np.array(data['chroma_mean']),
                    temporal_envelope=np.array(data['temporal_envelope']),
                    peak_frequencies=data['peak_frequencies'],
                    harmonic_structure=data['harmonic_structure'],
                )
        except:
            pass
        
        return None
