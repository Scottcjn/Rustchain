#!/usr/bin/env python3
"""
Ergo Anchor Chain Proof Verifier
================================

Independent audit tool for verifying Ergo anchor chain proofs.
Provides cryptographic verification of RustChain state commitments
anchored to the Ergo blockchain.

Features:
- Merkle proof verification
- Anchor transaction validation
- Commitment hash verification
- Multi-anchor chain verification
- Proof generation and export
- Batch verification support
"""

import os
import json
import hashlib
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ANCHOR-VERIFY] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS AND CONFIGURATION
# =============================================================================

class NetworkType(Enum):
    """Ergo network types."""
    MAINNET = "mainnet"
    TESTNET = "testnet"
    LOCAL = "local"


# Network configuration
NETWORK_CONFIG = {
    NetworkType.MAINNET: {
        "explorer_api": "https://api.ergoplatform.com",
        "node_url": "https://nodes.ergoplatform.com",
        "chain_id": 0
    },
    NetworkType.TESTNET: {
        "explorer_api": "https://api.testnet.ergoplatform.com",
        "node_url": "https://nodes.testnet.ergoplatform.com",
        "chain_id": 1
    },
    NetworkType.LOCAL: {
        "explorer_api": "http://localhost:9053",
        "node_url": "http://localhost:9053",
        "chain_id": 2
    }
}

# Verification parameters
DEFAULT_CONFIRMATION_DEPTH = 6
MAX_ANCHOR_AGE_BLOCKS = 10000
ANCHOR_REGISTER_ID = "R5"  # Register containing commitment hash


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class AnchorProof:
    """
    Cryptographic proof of an anchor on Ergo.
    
    Contains all necessary data to independently verify
    that a RustChain state was anchored to Ergo.
    """
    # Anchor identification
    tx_id: str                          # Ergo transaction ID
    block_id: str                       # Ergo block ID containing the tx
    block_height: int                   # Ergo block height
    
    # RustChain state commitment
    rustchain_height: int               # RustChain block height
    rustchain_hash: str                 # RustChain block hash (hex)
    state_root: str                     # State merkle root (hex)
    attestations_root: str              # Attestations merkle root (hex)
    
    # Commitment verification
    commitment_hash: str                # Blake2b256 commitment (hex)
    commitment_register: str            # Register ID (e.g., "R5")
    commitment_value: str               # Value stored in register (hex)
    
    # Timestamp and confirmations
    timestamp: int                      # Unix timestamp (ms)
    confirmations: int                  # Number of confirmations
    
    # Merkle proof (optional, for inclusion proofs)
    merkle_proof: List[str] = field(default_factory=list)  # Merkle path
    output_index: int = 0               # Output index in transaction
    
    # Metadata
    network: str = "mainnet"
    verified: bool = False
    verification_time: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AnchorProof":
        """Create from dictionary."""
        return cls(**data)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AnchorProof":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class VerificationResult:
    """Result of anchor proof verification."""
    is_valid: bool                      # Overall validity
    proof: AnchorProof                  # The proof that was verified
    
    # Individual checks
    tx_exists: bool = False             # Transaction exists on Ergo
    tx_confirmed: bool = False          # Transaction has confirmations
    commitment_matches: bool = False    # Commitment hash matches
    register_valid: bool = False        # Register format is correct
    merkle_valid: bool = False          # Merkle proof is valid
    timestamp_valid: bool = False       # Timestamp is reasonable
    rustchain_hash_valid: bool = False  # RustChain hash format valid
    
    # Error details
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Performance
    verification_time_ms: float = 0.0
    verifier_version: str = "1.0.0"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        result = asdict(self)
        result['proof'] = self.proof.to_dict()
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "✅ VALID" if self.is_valid else "❌ INVALID"
        lines = [
            f"Verification Status: {status}",
            f"Transaction ID: {self.proof.tx_id[:16]}...",
            f"RustChain Height: {self.proof.rustchain_height}",
            f"Confirmations: {self.proof.confirmations}",
            f"Verification Time: {self.verification_time_ms:.2f}ms",
        ]
        
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  - {warn}")
        
        return "\n".join(lines)


# =============================================================================
# CRYPTOGRAPHIC UTILITIES
# =============================================================================

class CryptoUtils:
    """Cryptographic utility functions."""
    
    @staticmethod
    def blake2b256(data: bytes) -> bytes:
        """Compute Blake2b-256 hash."""
        return hashlib.blake2b(data, digest_size=32).digest()
    
    @staticmethod
    def blake2b256_hex(data: bytes) -> str:
        """Compute Blake2b-256 hash as hex string."""
        return CryptoUtils.blake2b256(data).hex()
    
    @staticmethod
    def canonical_json(obj: Any) -> str:
        """Generate canonical JSON representation."""
        return json.dumps(obj, sort_keys=True, separators=(',', ':'))
    
    @staticmethod
    def compute_commitment_hash(
        rustchain_height: int,
        rustchain_hash: str,
        state_root: str,
        attestations_root: str,
        timestamp: int
    ) -> str:
        """
        Compute anchor commitment hash.
        
        The commitment hash is computed from the canonical JSON
        representation of the anchor data.
        """
        data = {
            "rc_height": rustchain_height,
            "rc_hash": rustchain_hash,
            "state_root": state_root,
            "attestations_root": attestations_root,
            "timestamp": timestamp
        }
        return CryptoUtils.blake2b256_hex(
            CryptoUtils.canonical_json(data).encode()
        )
    
    @staticmethod
    def verify_merkle_proof(
        leaf: bytes,
        proof: List[str],
        root: str
    ) -> bool:
        """
        Verify a Merkle proof.
        
        Args:
            leaf: The leaf node (preimage)
            proof: List of sibling hashes (hex strings)
            root: Expected Merkle root (hex string)
        
        Returns:
            True if proof is valid, False otherwise
        """
        try:
            current_hash = CryptoUtils.blake2b256(leaf)
            
            for i, sibling_hex in enumerate(proof):
                sibling = bytes.fromhex(sibling_hex)
                # Determine order based on position
                if i % 2 == 0:
                    combined = current_hash + sibling
                else:
                    combined = sibling + current_hash
                current_hash = CryptoUtils.blake2b256(combined)
            
            return current_hash.hex() == root
        except Exception as e:
            logger.error(f"Merkle proof verification error: {e}")
            return False
    
    @staticmethod
    def validate_hex_string(hex_str: str, expected_length: int = 64) -> bool:
        """Validate a hex string."""
        try:
            if not hex_str or len(hex_str) != expected_length:
                return False
            bytes.fromhex(hex_str)
            return True
        except ValueError:
            return False


# =============================================================================
# ERGO EXPLORER CLIENT
# =============================================================================

class ErgoExplorerClient:
    """Client for Ergo Explorer API."""
    
    def __init__(self, network: NetworkType = NetworkType.MAINNET):
        self.network = network
        self.config = NETWORK_CONFIG[network]
        self.base_url = self.config["explorer_api"].rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'ErgoAnchorVerifier/1.0.0'
        })
    
    def _get(self, endpoint: str, timeout: int = 30) -> Optional[Dict]:
        """Make GET request."""
        try:
            url = f"{self.base_url}{endpoint}"
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return None
            else:
                logger.error(f"Explorer API error: {resp.status_code} - {resp.text[:100]}")
                return None
        except requests.RequestException as e:
            logger.error(f"Explorer API request failed: {e}")
            return None
    
    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get transaction by ID."""
        return self._get(f"/api/v1/transactions/{tx_id}")
    
    def get_block_by_id(self, block_id: str) -> Optional[Dict]:
        """Get block by ID."""
        return self._get(f"/api/v1/blocks/{block_id}")
    
    def get_block_by_height(self, height: int) -> Optional[Dict]:
        """Get block by height."""
        return self._get(f"/api/v1/blocks/byHeight/{height}")
    
    def get_transaction_status(self, tx_id: str) -> Optional[Dict]:
        """Get transaction inclusion status."""
        return self._get(f"/api/v1/transactions/{tx_id}/status")
    
    def get_current_height(self) -> int:
        """Get current blockchain height."""
        blocks = self._get("/api/v1/blocks?limit=1")
        if blocks and 'items' in blocks and blocks['items']:
            return blocks['items'][0].get('height', 0)
        return 0
    
    def verify_output_register(
        self,
        tx: Dict,
        register_id: str,
        expected_value: str
    ) -> Tuple[bool, str]:
        """
        Verify that a transaction output contains expected register value.
        
        Returns (is_valid, actual_value)
        """
        try:
            outputs = tx.get('outputs', [])
            for output in outputs:
                registers = output.get('additionalRegisters', {})
                if register_id in registers:
                    reg_value = registers[register_id]
                    # Handle serialized value
                    if isinstance(reg_value, dict):
                        actual = reg_value.get('serializedValue', '')
                        # Remove type prefix (e.g., "0e40" for Coll[Byte])
                        if actual.startswith('0e40'):
                            actual = actual[4:]
                    else:
                        actual = str(reg_value)
                    
                    if actual.lower() == expected_value.lower():
                        return True, actual
                    else:
                        return False, actual
            
            return False, ""
        except Exception as e:
            logger.error(f"Register verification error: {e}")
            return False, ""


# =============================================================================
# ANCHOR PROOF VERIFIER
# =============================================================================

class AnchorProofVerifier:
    """
    Independent verifier for Ergo anchor chain proofs.
    
    Provides comprehensive verification of anchor proofs including:
    - Transaction existence and confirmation
    - Commitment hash verification
    - Register value validation
    - Merkle proof verification
    - Timestamp validation
    """
    
    def __init__(
        self,
        network: NetworkType = NetworkType.MAINNET,
        confirmation_depth: int = DEFAULT_CONFIRMATION_DEPTH
    ):
        self.network = network
        self.confirmation_depth = confirmation_depth
        self.explorer = ErgoExplorerClient(network)
        self.version = "1.0.0"
    
    def verify_proof(
        self,
        proof: AnchorProof,
        full_verification: bool = True
    ) -> VerificationResult:
        """
        Verify an anchor proof.
        
        Args:
            proof: The anchor proof to verify
            full_verification: If True, perform all verification checks
        
        Returns:
            VerificationResult with detailed status
        """
        start_time = time.time()
        result = VerificationResult(is_valid=True, proof=proof)
        
        try:
            # 1. Verify transaction exists
            tx = self.explorer.get_transaction(proof.tx_id)
            if not tx:
                result.is_valid = False
                result.errors.append(f"Transaction {proof.tx_id} not found")
                result.verification_time_ms = (time.time() - start_time) * 1000
                return result
            
            result.tx_exists = True
            
            # 2. Verify transaction confirmations
            tx_status = self.explorer.get_transaction_status(proof.tx_id)
            if tx_status:
                confirmations = tx_status.get('confirmations', 0)
                proof.confirmations = confirmations
                result.tx_confirmed = confirmations >= self.confirmation_depth
                
                if not result.tx_confirmed:
                    result.warnings.append(
                        f"Transaction has {confirmations} confirmations "
                        f"(required: {self.confirmation_depth})"
                    )
            else:
                result.warnings.append("Could not fetch transaction status")
            
            # 3. Verify commitment hash format
            if not CryptoUtils.validate_hex_string(proof.commitment_hash, 64):
                result.is_valid = False
                result.errors.append("Invalid commitment hash format")
            else:
                result.rustchain_hash_valid = True
            
            # 4. Verify register contains commitment
            register_valid, actual_value = self.explorer.verify_output_register(
                tx, proof.commitment_register, proof.commitment_value
            )
            result.register_valid = register_valid
            
            if not register_valid:
                result.is_valid = False
                result.errors.append(
                    f"Register {proof.commitment_register} value mismatch. "
                    f"Expected: {proof.commitment_value[:16]}..., "
                    f"Got: {actual_value[:16] if actual_value else 'N/A'}..."
                )
            
            # 5. Verify commitment hash matches stored value
            if proof.commitment_hash.lower() != proof.commitment_value.lower():
                result.is_valid = False
                result.errors.append(
                    "Commitment hash does not match register value"
                )
            else:
                result.commitment_matches = True
            
            # 6. Recompute and verify commitment hash
            computed_hash = CryptoUtils.compute_commitment_hash(
                proof.rustchain_height,
                proof.rustchain_hash,
                proof.state_root,
                proof.attestations_root,
                proof.timestamp
            )
            
            if computed_hash.lower() != proof.commitment_hash.lower():
                result.is_valid = False
                result.errors.append(
                    f"Computed commitment hash mismatch. "
                    f"Expected: {computed_hash[:16]}..., "
                    f"Got: {proof.commitment_hash[:16]}..."
                )
            else:
                result.commitment_matches = True
            
            # 7. Verify Merkle proof (if provided)
            if full_verification and proof.merkle_proof:
                leaf_data = json.dumps({
                    "height": proof.rustchain_height,
                    "hash": proof.rustchain_hash
                }, sort_keys=True).encode()
                
                merkle_valid = CryptoUtils.verify_merkle_proof(
                    leaf_data,
                    proof.merkle_proof,
                    proof.state_root
                )
                result.merkle_valid = merkle_valid
                
                if not merkle_valid:
                    result.warnings.append("Merkle proof verification failed")
            
            # 8. Verify timestamp
            current_time = int(time.time() * 1000)
            time_diff = current_time - proof.timestamp
            
            if time_diff < 0:
                result.is_valid = False
                result.errors.append("Timestamp is in the future")
            elif time_diff > MAX_ANCHOR_AGE_BLOCKS * 2 * 60 * 1000:  # ~2 blocks/min
                result.warnings.append("Anchor is very old")
            else:
                result.timestamp_valid = True
            
            # 9. Verify block inclusion
            if proof.block_id:
                block = self.explorer.get_block_by_id(proof.block_id)
                if not block:
                    result.warnings.append(f"Block {proof.block_id} not found")
                else:
                    # Verify transaction is in block
                    block_txs = block.get('transactions', [])
                    if proof.tx_id not in block_txs:
                        result.is_valid = False
                        result.errors.append("Transaction not in specified block")
        
        except Exception as e:
            result.is_valid = False
            result.errors.append(f"Verification error: {str(e)}")
            logger.exception("Verification exception")
        
        # Record verification time
        result.verification_time_ms = (time.time() - start_time) * 1000
        result.verifier_version = self.version
        
        # Update proof verification status
        proof.verified = result.is_valid
        proof.verification_time = result.verification_time_ms
        
        return result
    
    def verify_from_transaction(
        self,
        tx_id: str,
        rustchain_height: int,
        expected_commitment: Optional[str] = None
    ) -> VerificationResult:
        """
        Verify an anchor directly from transaction ID.
        
        This method fetches transaction data from Ergo explorer and
        extracts the anchor proof automatically.
        
        Args:
            tx_id: Ergo transaction ID
            rustchain_height: Expected RustChain height
            expected_commitment: Expected commitment hash (optional)
        
        Returns:
            VerificationResult with extracted and verified proof
        """
        # Fetch transaction
        tx = self.explorer.get_transaction(tx_id)
        if not tx:
            return VerificationResult(
                is_valid=False,
                proof=AnchorProof(
                    tx_id=tx_id,
                    rustchain_height=rustchain_height,
                    block_id="",
                    block_height=0,
                    rustchain_hash="",
                    state_root="",
                    attestations_root="",
                    commitment_hash="",
                    commitment_register="",
                    commitment_value="",
                    timestamp=0,
                    confirmations=0
                ),
                errors=["Transaction not found"]
            )
        
        # Extract anchor data from transaction registers
        commitment_hash = ""
        commitment_register = ""
        commitment_value = ""
        rustchain_hash = ""
        state_root = ""
        attestations_root = ""
        timestamp = 0
        output_index = 0
        
        for idx, output in enumerate(tx.get('outputs', [])):
            registers = output.get('additionalRegisters', {})
            
            # Look for commitment in registers
            for reg_id in ['R4', 'R5', 'R6', 'R7']:
                if reg_id in registers:
                    reg_value = registers[reg_id]
                    if isinstance(reg_value, dict):
                        serialized = reg_value.get('serializedValue', '')
                        if serialized.startswith('0e40'):
                            # Found commitment hash
                            commitment_hash = serialized[4:]
                            commitment_register = reg_id
                            commitment_value = serialized
                            output_index = idx
                            break
            
            # Try to extract other data from registers
            if 'R4' in registers:
                # R4 might contain RustChain height
                pass
        
        # Get block information
        block_id = tx.get('blockId', '')
        block_height = tx.get('blockHeight', 0)
        
        # Get confirmations
        confirmations = 0
        tx_status = self.explorer.get_transaction_status(tx_id)
        if tx_status:
            confirmations = tx_status.get('confirmations', 0)
        
        # Construct proof
        proof = AnchorProof(
            tx_id=tx_id,
            block_id=block_id,
            block_height=block_height,
            rustchain_height=rustchain_height,
            rustchain_hash=rustchain_hash,
            state_root=state_root,
            attestations_root=attestations_root,
            commitment_hash=commitment_hash,
            commitment_register=commitment_register,
            commitment_value=commitment_value,
            timestamp=timestamp,
            confirmations=confirmations,
            output_index=output_index,
            network=self.network.value
        )
        
        # Verify the proof
        return self.verify_proof(proof)
    
    def batch_verify(
        self,
        proofs: List[AnchorProof],
        parallel: bool = False
    ) -> List[VerificationResult]:
        """
        Verify multiple anchor proofs.
        
        Args:
            proofs: List of proofs to verify
            parallel: If True, verify in parallel (not implemented)
        
        Returns:
            List of verification results
        """
        results = []
        for proof in proofs:
            result = self.verify_proof(proof)
            results.append(result)
        return results
    
    def generate_audit_report(
        self,
        results: List[VerificationResult],
        output_path: Optional[str] = None
    ) -> str:
        """
        Generate an audit report from verification results.
        
        Args:
            results: List of verification results
            output_path: Optional path to save report
        
        Returns:
            Report content as string
        """
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        
        report_lines = [
            "=" * 70,
            "ERGO ANCHOR CHAIN PROOF VERIFICATION AUDIT REPORT",
            "=" * 70,
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Verifier Version: {self.version}",
            f"Network: {self.network.value}",
            "",
            "SUMMARY",
            "-" * 70,
            f"Total Proofs Verified: {total}",
            f"Valid: {valid} ({100*valid/total:.1f}%)",
            f"Invalid: {invalid} ({100*invalid/total:.1f}%)",
            "",
            "DETAILED RESULTS",
            "-" * 70,
        ]
        
        for i, result in enumerate(results, 1):
            status = "✅ PASS" if result.is_valid else "❌ FAIL"
            report_lines.extend([
                "",
                f"Proof #{i}: {status}",
                f"  Transaction: {result.proof.tx_id}",
                f"  RustChain Height: {result.proof.rustchain_height}",
                f"  Confirmations: {result.proof.confirmations}",
                f"  Verification Time: {result.verification_time_ms:.2f}ms",
            ])
            
            if result.errors:
                report_lines.append("  Errors:")
                for err in result.errors:
                    report_lines.append(f"    - {err}")
            
            if result.warnings:
                report_lines.append("  Warnings:")
                for warn in result.warnings:
                    report_lines.append(f"    - {warn}")
        
        report_lines.extend([
            "",
            "=" * 70,
            "END OF REPORT",
            "=" * 70,
        ])
        
        report = "\n".join(report_lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
            logger.info(f"Audit report saved to {output_path}")
        
        return report


# =============================================================================
# PROOF GENERATION
# =============================================================================

class AnchorProofGenerator:
    """
    Generate anchor proofs from Ergo transactions.
    """
    
    def __init__(self, network: NetworkType = NetworkType.MAINNET):
        self.network = network
        self.explorer = ErgoExplorerClient(network)
    
    def generate_from_transaction(
        self,
        tx_id: str,
        rustchain_height: int,
        rustchain_hash: str,
        state_root: str,
        attestations_root: str
    ) -> Optional[AnchorProof]:
        """
        Generate an anchor proof from a transaction.
        
        Args:
            tx_id: Ergo transaction ID
            rustchain_height: RustChain block height
            rustchain_hash: RustChain block hash
            state_root: State merkle root
            attestations_root: Attestations merkle root
        
        Returns:
            AnchorProof if successful, None otherwise
        """
        tx = self.explorer.get_transaction(tx_id)
        if not tx:
            logger.error(f"Transaction {tx_id} not found")
            return None
        
        # Extract commitment from registers
        commitment_hash = ""
        commitment_register = ""
        commitment_value = ""
        timestamp = 0
        output_index = 0
        
        for idx, output in enumerate(tx.get('outputs', [])):
            registers = output.get('additionalRegisters', {})
            
            for reg_id in ['R4', 'R5', 'R6', 'R7']:
                if reg_id in registers:
                    reg_value = registers[reg_id]
                    if isinstance(reg_value, dict):
                        serialized = reg_value.get('serializedValue', '')
                        if serialized.startswith('0e40') and len(serialized) == 68:
                            commitment_hash = serialized[4:]
                            commitment_register = reg_id
                            commitment_value = serialized
                            output_index = idx
                            break
        
        if not commitment_hash:
            logger.error("No commitment found in transaction registers")
            return None
        
        # Get block information
        block_id = tx.get('blockId', '')
        block_height = tx.get('blockHeight', 0)
        
        # Get confirmations
        confirmations = 0
        tx_status = self.explorer.get_transaction_status(tx_id)
        if tx_status:
            confirmations = tx_status.get('confirmations', 0)
        
        # Compute timestamp from block if available
        timestamp = int(time.time() * 1000)
        if block_id:
            block = self.explorer.get_block_by_id(block_id)
            if block:
                timestamp = block.get('timestamp', timestamp)
        
        return AnchorProof(
            tx_id=tx_id,
            block_id=block_id,
            block_height=block_height,
            rustchain_height=rustchain_height,
            rustchain_hash=rustchain_hash,
            state_root=state_root,
            attestations_root=attestations_root,
            commitment_hash=commitment_hash,
            commitment_register=commitment_register,
            commitment_value=commitment_value,
            timestamp=timestamp,
            confirmations=confirmations,
            output_index=output_index,
            network=self.network.value
        )


# =============================================================================
# CLI INTERFACE
# =============================================================================

def create_cli():
    """Create command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ergo Anchor Chain Proof Verifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify a proof from JSON file
  %(prog)s verify --proof proof.json
  
  # Verify a transaction directly
  %(prog)s verify-tx <tx_id> --height <rustchain_height>
  
  # Generate a proof from transaction
  %(prog)s generate --tx <tx_id> --height <height> --hash <rc_hash>
  
  # Batch verify multiple proofs
  %(prog)s batch --proofs proof1.json proof2.json
  
  # Generate audit report
  %(prog)s audit --proofs *.json --output report.txt
        """
    )
    
    parser.add_argument(
        '--network',
        choices=['mainnet', 'testnet', 'local'],
        default='mainnet',
        help='Ergo network (default: mainnet)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Verify command
    verify_parser = subparsers.add_parser(
        'verify',
        help='Verify an anchor proof'
    )
    verify_parser.add_argument(
        '--proof', '-p',
        required=True,
        help='Path to proof JSON file'
    )
    verify_parser.add_argument(
        '--full',
        action='store_true',
        help='Perform full verification including Merkle proofs'
    )
    
    # Verify transaction command
    verify_tx_parser = subparsers.add_parser(
        'verify-tx',
        help='Verify an anchor from transaction ID'
    )
    verify_tx_parser.add_argument(
        'tx_id',
        help='Ergo transaction ID'
    )
    verify_tx_parser.add_argument(
        '--height', '-H',
        type=int,
        required=True,
        help='RustChain block height'
    )
    verify_tx_parser.add_argument(
        '--commitment', '-c',
        help='Expected commitment hash'
    )
    
    # Generate command
    generate_parser = subparsers.add_parser(
        'generate',
        help='Generate an anchor proof from transaction'
    )
    generate_parser.add_argument(
        '--tx', '-t',
        required=True,
        help='Ergo transaction ID'
    )
    generate_parser.add_argument(
        '--height', '-H',
        type=int,
        required=True,
        help='RustChain block height'
    )
    generate_parser.add_argument(
        '--hash',
        required=True,
        help='RustChain block hash'
    )
    generate_parser.add_argument(
        '--state-root',
        required=True,
        help='State merkle root'
    )
    generate_parser.add_argument(
        '--attestations-root',
        required=True,
        help='Attestations merkle root'
    )
    generate_parser.add_argument(
        '--output', '-o',
        help='Output file path'
    )
    
    # Batch command
    batch_parser = subparsers.add_parser(
        'batch',
        help='Batch verify multiple proofs'
    )
    batch_parser.add_argument(
        '--proofs', '-p',
        nargs='+',
        required=True,
        help='Paths to proof JSON files'
    )
    
    # Audit command
    audit_parser = subparsers.add_parser(
        'audit',
        help='Generate audit report'
    )
    audit_parser.add_argument(
        '--proofs', '-p',
        nargs='+',
        required=True,
        help='Paths to proof JSON files'
    )
    audit_parser.add_argument(
        '--output', '-o',
        help='Output report file path'
    )
    
    return parser


def main():
    """Main entry point."""
    import sys
    
    parser = create_cli()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize verifier
    network = NetworkType(args.network)
    verifier = AnchorProofVerifier(network=network)
    
    try:
        if args.command == 'verify':
            # Verify proof from file
            with open(args.proof, 'r') as f:
                proof = AnchorProof.from_json(f.read())
            
            result = verifier.verify_proof(proof, full_verification=args.full)
            print(result.summary())
            
            if not result.is_valid:
                sys.exit(1)
        
        elif args.command == 'verify-tx':
            # Verify transaction directly
            result = verifier.verify_from_transaction(
                args.tx_id,
                args.height,
                args.commitment
            )
            print(result.summary())
            
            if not result.is_valid:
                sys.exit(1)
        
        elif args.command == 'generate':
            # Generate proof from transaction
            generator = AnchorProofGenerator(network=network)
            proof = generator.generate_from_transaction(
                args.tx,
                args.height,
                args.hash,
                args.state_root,
                args.attestations_root
            )
            
            if proof:
                proof_json = proof.to_json()
                
                if args.output:
                    with open(args.output, 'w') as f:
                        f.write(proof_json)
                    print(f"Proof saved to {args.output}")
                else:
                    print(proof_json)
            else:
                print("Failed to generate proof", file=sys.stderr)
                sys.exit(1)
        
        elif args.command == 'batch':
            # Batch verify
            results = []
            for proof_path in args.proofs:
                with open(proof_path, 'r') as f:
                    proof = AnchorProof.from_json(f.read())
                result = verifier.verify_proof(proof)
                results.append(result)
                status = "✅" if result.is_valid else "❌"
                print(f"{status} {proof_path}: {result.summary().split(chr(10))[0]}")
            
            # Summary
            valid = sum(1 for r in results if r.is_valid)
            print(f"\n{valid}/{len(results)} proofs valid")
            
            if valid != len(results):
                sys.exit(1)
        
        elif args.command == 'audit':
            # Generate audit report
            results = []
            for proof_path in args.proofs:
                with open(proof_path, 'r') as f:
                    proof = AnchorProof.from_json(f.read())
                result = verifier.verify_proof(proof)
                results.append(result)
            
            report = verifier.generate_audit_report(results, args.output)
            print(report)
        
        else:
            parser.print_help()
            sys.exit(1)
    
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Unexpected error")
        sys.exit(1)


if __name__ == "__main__":
    main()
