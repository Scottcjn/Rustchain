# RustChain API Reference Documentation

This comprehensive API reference provides complete documentation for all RustChain node endpoints, including:

- **Public endpoints** (no authentication required)
- **Authenticated endpoints** (require X-Admin-Key header)
- **Miner attestation endpoints**
- **Wallet operations**
- **Network status and monitoring**

## Features

✅ **Complete endpoint coverage** - All documented endpoints from issue #213  
✅ **Real-world examples** - Practical curl commands with actual responses  
✅ **Field name accuracy** - Uses exact field names from API responses  
✅ **Error handling** - Common mistakes and error codes documented  
✅ **OpenAPI 3.0 specification** - Machine-readable API definition  
✅ **HTTPS guidance** - Self-signed certificate handling instructions  

## Usage

The documentation is organized by endpoint type:

1. **Health & Status** - Node health checks and readiness probes
2. **Epoch Information** - Current epoch, slot, and reward pool data  
3. **Network Data** - Miners list, nodes, and network statistics
4. **Wallet Queries** - Balance checking and transaction history
5. **Block Explorer** - Web UI access
6. **Authenticated Endpoints** - Admin-only operations
7. **RIP-200 Attestation** - Miner integration endpoints

## Validation

All examples have been tested against the live RustChain node at `https://50.28.86.131`.

## Contributing

If you find any discrepancies or missing information, please open an issue or submit a PR.

---

*Documentation generated for RustChain v2.2.1-rip200*
*Addresses GitHub Issue #213: "📚 API Reference — Official Endpoint Documentation"*