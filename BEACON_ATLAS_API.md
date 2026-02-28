# Beacon Atlas API Documentation

## Overview
The Beacon Atlas API provides secure communication and attestation services for RustChain nodes.

## Endpoints

### `/relay/ping`
- **Method**: GET
- **Description**: Health check endpoint for relay nodes
- **Response**: `{"status": "ok", "timestamp": "ISO8601"}`

### `/relay/attest`
- **Method**: POST  
- **Description**: Submit hardware attestation data
- **Request Body**: JSON with hardware fingerprint
- **Response**: `{"success": true, "node_id": "string"}`

### `/api/miners`
- **Method**: GET
- **Description**: Get list of active miners
- **Response**: Array of miner objects

## TOFU (Trust On First Use) Key Management

### Key Generation
- Each node generates a unique key pair on first startup
- Public key is registered with the network
- Private key is stored securely on the node

### Key Verification  
- All communications are signed with the node's private key
- Recipients verify signatures using the registered public key
- Keys are never transmitted over the network

### Key Rotation
- Automatic key rotation every 30 days
- Old keys remain valid for 7 days during transition period
- New attestations use the rotated key immediately

## Security Considerations

- **Hardware Fingerprinting**: Real hardware only, VMs earn nothing
- **Anti-emulation**: 6-point hardware fingerprint prevents spoofing  
- **Epoch Rewards**: 1.5 RTC distributed per epoch to active miners

## Usage Examples

### Node Registration
```bash
curl -X POST https://50.28.86.131/relay/attest \
  -H "Content-Type: application/json" \
  -d '{"hardware_fingerprint": "your_fingerprint_data"}'
```

### Health Check
```bash
curl https://50.28.86.131/relay/ping
```

### Get Miners List
```bash
curl https://50.28.86.131/api/miners
```

## Integration Guide

1. **Setup**: Configure your node with proper hardware fingerprinting
2. **Registration**: Register your node using the `/relay/attest` endpoint  
3. **Monitoring**: Use `/relay/ping` for health monitoring
4. **Verification**: Verify other nodes using their public keys

---

*This documentation provides a pure technical reference for the Beacon Atlas API and TOFU key management system.*