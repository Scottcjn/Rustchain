# RustChain <-> Ergo Network Bridge & Spectrum DEX Integration

Bridge implementation and ErgoScript contract connecting RustChain Proof-of-Antiquity (RTC) to the Ergo blockchain (eRTC) and Spectrum Finance DEX (resolving Bounty Scottcjn/Rustchain#32 Milestone 1 & 2).

## Architecture
1. **EIP-4 Native Token Standard**:
   - `name`: "RustChain Token"
   - `symbol`: "RTC"
   - `decimals`: 6 (1 eRTC = 1,000,000 uRTC)
2. **ErgoScript Bridge Contract (`contracts/ErgoRTCBridge.es`)**:
   - Implements 2-of-3 threshold multisig operator verification for minting/releasing `eRTC` on Ergo.
   - Enforces token burning and recipient R4 register binding when users burn `eRTC` to redeem native `RTC`.
3. **Daemon & Relay Service (`bridge_daemon.py`)**:
   - Ingests lock and burn events across nodes.
   - Verifies address formats and ensures zero-loss conservation.

## Spectrum DEX Integration (Milestone 3)
- Pool Pair: `eRTC / ERG`
- Initial Reference Ratio: `1 RTC = 0.067 ERG` (~$0.10 reference at $1.50/ERG).
- Automated AMM pool provisioning via Spectrum Finance contract standards.

## Testing
```bash
pytest bridges/ergo/tests/test_ergo_bridge.py
```
