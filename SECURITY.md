# Security Policy

## Reporting a Vulnerability

Do not open public issues for critical vulnerabilities before maintainers can patch.

- Use responsible disclosure via project maintainers.
- Include reproduction steps, impact, and proposed mitigation.

## Key Management Best Practices

### Ed25519 Key Security

RustChain uses Ed25519 signatures for all authenticated operations. Follow these best practices:

1. **Secure Key Storage**: Store private keys in secure locations (hardware wallets, encrypted storage)
2. **Key Backup**: Always backup your private keys securely - lost keys cannot be recovered
3. **Key Rotation**: Regularly rotate keys using the TOFU key rotation functionality
4. **Compromise Response**: Immediately revoke compromised keys using the key revocation API

### TOFU (Trust-On-First-Use) Security Model

RustChain implements TOFU key management for beacon agents:

- **Initial Trust**: The first public key registered for an agent is trusted permanently
- **Key Validation**: All subsequent communications must be signed with the registered key
- **Revocation**: Compromised keys can be revoked to prevent unauthorized access
- **Rotation**: Keys can be safely rotated with proper authentication

### Anti-Emulation Protection

The hardware fingerprinting system includes multiple layers of anti-emulation protection:

- **Clock Skew Detection**: Real hardware has unique oscillator drift patterns
- **Cache Timing**: VMs cannot perfectly replicate cache timing characteristics  
- **SIMD Identity**: Vector unit behavior is hardware-specific
- **Thermal Entropy**: Heat patterns are unique to physical silicon
- **Instruction Jitter**: Microarchitectural timing varies by real hardware
- **Behavioral Heuristics**: Advanced detection of virtualization artifacts

### Rate Limiting

API endpoints are protected by rate limiting:

- **Public endpoints**: 100 requests/minute
- **Attestation**: 1 per 10 minutes per miner  
- **Transfers**: 10 per minute per wallet
- **Beacon Atlas**: Protected against abuse and DoS attacks

### Secure Communication

All API communication should use HTTPS with proper certificate validation:

- **Production**: Valid certificates from trusted CAs
- **Development**: Self-signed certificates (use `-k` flag with curl)
- **Authentication**: All sensitive operations require Ed25519 signatures
- **Authorization**: Proper access controls prevent unauthorized operations

## Security Headers

The RustChain API implements appropriate security headers:

- **Content-Security-Policy**: Prevents XSS attacks
- **X-Content-Type-Options**: Prevents MIME type sniffing
- **X-Frame-Options**: Prevents clickjacking
- **Strict-Transport-Security**: Enforces HTTPS

## Regular Security Updates

- Monitor dependencies for security vulnerabilities
- Apply security patches promptly
- Follow security best practices for Python and Flask applications
- Keep system and runtime updated

## Contact

For security concerns, contact the maintainers through official channels.