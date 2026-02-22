# TOFU Key Revocation and Rotation

## Overview

This document describes the Trust On First Use (TOFU) key management system implemented for RustChain. The system provides secure key revocation and rotation capabilities to enhance the overall security posture of the network.

## Features

- **Secure Key Storage**: Keys are stored in an encrypted JSON format with proper access controls
- **Key Revocation**: Ability to revoke compromised or outdated keys with audit logging
- **Key Rotation**: Seamless key rotation with backward compatibility and history tracking
- **Validation**: Built-in validation to ensure only valid keys are accepted

## Implementation Details

### Key Structure

Each key entry contains:
- `key`: The actual key material (hashed for demonstration)
- `key_type`: The cryptographic algorithm used (e.g., ed25519)
- `created_at`: Timestamp of key creation
- `revoked`: Boolean flag indicating if the key has been revoked
- `revoked_at`: Timestamp of revocation (if applicable)
- `revocation_reason`: Reason for revocation
- `rotation_history`: History of key rotations

### Security Considerations

- All key operations are logged for audit purposes
- Keys are validated before use to prevent using revoked keys
- The system prevents duplicate key generation for the same node
- Proper error handling ensures system stability

## Integration

The TOFU key manager is integrated into the RustChain node security module and can be accessed through the standard security API.

## Testing

Comprehensive test coverage ensures the reliability and correctness of the implementation. Tests include:
- Key generation
- Key revocation
- Key rotation
- Validation scenarios
- Edge cases and error conditions

## Usage

```python
from node.security.tofu_key_manager import TOFUKeyManager

# Initialize key manager
key_manager = TOFUKeyManager("path/to/key/store.json")

# Generate a new key
key = key_manager.generate_key("node_123")

# Validate a key
if key_manager.is_key_valid("node_123"):
    # Use the key for operations
    pass

# Revoke a compromised key
key_manager.revoke_key("node_123", "Suspected compromise")

# Rotate a key for regular maintenance
new_key = key_manager.rotate_key("node_123")
```

## Related Issues

- Fixes #308: TOFU Key Revocation and Rotation — 15 RTC bounty