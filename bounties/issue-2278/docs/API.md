# Ergo Anchor Chain Proof Verifier - API Documentation

## Module Overview

The `ergo_anchor_verifier` module provides comprehensive tools for verifying Ergo anchor chain proofs.

## Classes

### NetworkType

Enum for Ergo network types.

```python
class NetworkType(Enum):
    MAINNET = "mainnet"
    TESTNET = "testnet"
    LOCAL = "local"
```

### AnchorProof

Data class representing an anchor proof.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `tx_id` | str | Ergo transaction ID (64 hex chars) |
| `block_id` | str | Ergo block ID containing the transaction |
| `block_height` | int | Ergo block height |
| `rustchain_height` | int | RustChain block height |
| `rustchain_hash` | str | RustChain block hash (64 hex chars) |
| `state_root` | str | State Merkle root (64 hex chars) |
| `attestations_root` | str | Attestations Merkle root (64 hex chars) |
| `commitment_hash` | str | Blake2b256 commitment hash (64 hex chars) |
| `commitment_register` | str | Register ID containing commitment (R4-R7) |
| `commitment_value` | str | Full register value with type prefix |
| `timestamp` | int | Unix timestamp in milliseconds |
| `confirmations` | int | Number of block confirmations |
| `merkle_proof` | List[str] | Merkle proof path (optional) |
| `output_index` | int | Output index in transaction |
| `network` | str | Network name |
| `verified` | bool | Verification status |
| `verification_time` | float | Verification time in ms |

#### Methods

```python
def to_dict() -> Dict
    """Convert to dictionary."""

def from_dict(data: Dict) -> AnchorProof
    """Create from dictionary."""

def to_json(indent: int = 2) -> str
    """Convert to JSON string."""

def from_json(json_str: str) -> AnchorProof
    """Create from JSON string."""
```

### VerificationResult

Data class representing verification result.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_valid` | bool | Overall validity |
| `proof` | AnchorProof | The proof that was verified |
| `tx_exists` | bool | Transaction exists on Ergo |
| `tx_confirmed` | bool | Transaction has sufficient confirmations |
| `commitment_matches` | bool | Commitment hash matches |
| `register_valid` | bool | Register format is correct |
| `merkle_valid` | bool | Merkle proof is valid |
| `timestamp_valid` | bool | Timestamp is reasonable |
| `rustchain_hash_valid` | bool | RustChain hash format valid |
| `errors` | List[str] | List of error messages |
| `warnings` | List[str] | List of warning messages |
| `verification_time_ms` | float | Verification time in milliseconds |
| `verifier_version` | str | Verifier version string |

#### Methods

```python
def to_dict() -> Dict
    """Convert to dictionary."""

def to_json(indent: int = 2) -> str
    """Convert to JSON string."""

def summary() -> str
    """Generate human-readable summary."""
```

### CryptoUtils

Cryptographic utility functions.

#### Methods

```python
@staticmethod
def blake2b256(data: bytes) -> bytes
    """Compute Blake2b-256 hash."""

@staticmethod
def blake2b256_hex(data: bytes) -> str
    """Compute Blake2b-256 hash as hex string."""

@staticmethod
def canonical_json(obj: Any) -> str
    """Generate canonical JSON representation."""

@staticmethod
def compute_commitment_hash(
    rustchain_height: int,
    rustchain_hash: str,
    state_root: str,
    attestations_root: str,
    timestamp: int
) -> str
    """Compute anchor commitment hash."""

@staticmethod
def verify_merkle_proof(
    leaf: bytes,
    proof: List[str],
    root: str
) -> bool
    """Verify a Merkle proof."""

@staticmethod
def validate_hex_string(hex_str: str, expected_length: int = 64) -> bool
    """Validate a hex string."""
```

### ErgoExplorerClient

Client for Ergo Explorer API.

#### Constructor

```python
def __init__(self, network: NetworkType = NetworkType.MAINNET)
```

#### Methods

```python
def get_transaction(tx_id: str) -> Optional[Dict]
    """Get transaction by ID."""

def get_block_by_id(block_id: str) -> Optional[Dict]
    """Get block by ID."""

def get_block_by_height(height: int) -> Optional[Dict]
    """Get block by height."""

def get_transaction_status(tx_id: str) -> Optional[Dict]
    """Get transaction inclusion status."""

def get_current_height() -> int
    """Get current blockchain height."""

def verify_output_register(
    tx: Dict,
    register_id: str,
    expected_value: str
) -> Tuple[bool, str]
    """Verify transaction output contains expected register value."""
```

### AnchorProofVerifier

Main verifier class.

#### Constructor

```python
def __init__(
    self,
    network: NetworkType = NetworkType.MAINNET,
    confirmation_depth: int = 6
)
```

#### Methods

```python
def verify_proof(
    proof: AnchorProof,
    full_verification: bool = True
) -> VerificationResult
    """Verify an anchor proof."""

def verify_from_transaction(
    self,
    tx_id: str,
    rustchain_height: int,
    expected_commitment: Optional[str] = None
) -> VerificationResult
    """Verify an anchor directly from transaction ID."""

def batch_verify(
    proofs: List[AnchorProof],
    parallel: bool = False
) -> List[VerificationResult]
    """Verify multiple anchor proofs."""

def generate_audit_report(
    results: List[VerificationResult],
    output_path: Optional[str] = None
) -> str
    """Generate an audit report from verification results."""
```

### AnchorProofGenerator

Generate anchor proofs from Ergo transactions.

#### Constructor

```python
def __init__(self, network: NetworkType = NetworkType.MAINNET)
```

#### Methods

```python
def generate_from_transaction(
    tx_id: str,
    rustchain_height: int,
    rustchain_hash: str,
    state_root: str,
    attestations_root: str
) -> Optional[AnchorProof]
    """Generate an anchor proof from a transaction."""
```

## Usage Examples

### Basic Verification

```python
from ergo_anchor_verifier import AnchorProofVerifier, AnchorProof, NetworkType

# Initialize
verifier = AnchorProofVerifier(network=NetworkType.MAINNET)

# Load proof
with open('proof.json', 'r') as f:
    proof = AnchorProof.from_json(f.read())

# Verify
result = verifier.verify_proof(proof)

# Check result
print(result.summary())
```

### Transaction Verification

```python
# Verify from transaction ID
result = verifier.verify_from_transaction(
    tx_id="a1b2c3d4...",
    rustchain_height=50000
)

if result.is_valid:
    print("Valid anchor!")
else:
    print("Errors:", result.errors)
```

### Batch Verification

```python
proofs = [proof1, proof2, proof3]
results = verifier.batch_verify(proofs)

valid_count = sum(1 for r in results if r.is_valid)
print(f"{valid_count}/{len(proofs)} proofs valid")
```

### Generate Proof

```python
from ergo_anchor_verifier import AnchorProofGenerator

generator = AnchorProofGenerator(network=NetworkType.MAINNET)

proof = generator.generate_from_transaction(
    tx_id="a1b2c3d4...",
    rustchain_height=50000,
    rustchain_hash="abc123...",
    state_root="def456...",
    attestations_root="ghi789..."
)

if proof:
    print(proof.to_json())
```

### Audit Report

```python
results = verifier.batch_verify(proofs)
report = verifier.generate_audit_report(results, output_path="audit.txt")
print(report)
```

## Error Handling

All methods handle errors gracefully and return appropriate error messages in the `VerificationResult`.

```python
result = verifier.verify_proof(proof)

if not result.is_valid:
    for error in result.errors:
        print(f"Error: {error}")
    
    for warning in result.warnings:
        print(f"Warning: {warning}")
```

## Constants

```python
DEFAULT_CONFIRMATION_DEPTH = 6
MAX_ANCHOR_AGE_BLOCKS = 10000
ANCHOR_REGISTER_ID = "R5"
```

## Network Configuration

```python
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
```
