# Registry Submission Status — 2026-03-24

## 1. mcp.so — ALREADY SUBMITTED (no action needed)

**Status**: DONE (submitted twice)

Two comments already exist on chatmcp/mcpso issue #1:
- **2026-03-09**: First submission by Scottcjn (comment ID 4020468145)
- **2026-03-16**: Second submission by Scottcjn (comment ID 4070009556)

No further action needed. Posting again would be spam.

**Verify**: https://github.com/chatmcp/mcpso/issues/1

---

## 2. DePINScan (depinscan.io) — REQUIRES BROWSER

**Status**: NOT YET SUBMITTED — requires manual browser interaction

DePINScan is a React web app with wallet-connect (RainbowKit) authentication.
There is no public API or GitHub repo for project submission.

### Steps to complete manually:
1. Go to https://depinscan.io/
2. Click "Developer" in the navbar
3. Sign in with GitHub (Scottcjn account)
4. Click "Add Project"
5. Fill out the 3 tabs using data from `depinscan_submission.md`:

**Config Tab:**
- Project Name: RustChain
- Description: (see depinscan_submission.md)
- Category: Compute/AI
- Token: RTC
- Website: https://rustchain.org
- GitHub: https://github.com/Scottcjn/rustchain
- Block Explorer: https://rustchain.org/explorer
- Total Devices: 18+
- Node Count: 4

**Tags Tab:**
- Proof of Work, Hardware Mining, Vintage Computing, Physical Infrastructure, Cross-chain, Ergo, PowerPC, Anti-Emulation, Hardware Fingerprinting

**Social Tab:**
- GitHub: https://github.com/Scottcjn
- Website: https://rustchain.org
- Documentation: https://rustchain.org/llms.txt

6. Submit and wait for IoTeX team review

**Note**: Need a logo PNG/SVG. Check repo for existing logo or create one.

---

## 3. DePINHub (depinhub.io) — REQUIRES DISCORD

**Status**: NOT YET SUBMITTED — requires Discord interaction

DePINHub uses Discord for project submissions. No web form or API.

### Steps to complete manually:
1. Go to https://depinhub.io/discord to join their Discord
2. Find the project submission or general channel
3. Post the prepared message from `depinhub_submission.md` (copied below for convenience):

```
Hi DePINHub team! I'd like to submit RustChain for your project listing.

**Project Name**: RustChain
**Website**: https://rustchain.org
**GitHub**: https://github.com/Scottcjn/rustchain

**Description**: RustChain is a DePIN blockchain that rewards real physical hardware through Proof-of-Antiquity (RIP-PoA). 7 hardware fingerprint checks verify authentic vintage and modern compute — G4 PowerBooks, SPARC workstations, POWER8 servers, and more. 4 attestation nodes across 3 continents, Ergo cross-chain anchoring, 31,710+ RTC distributed to 248+ contributors.

**Category**: Compute / Hardware Infrastructure

**Key Differentiators**:
- Proof-of-Antiquity: vintage hardware earns higher rewards (G4 = 2.5x, SPARC = 2.9x)
- 7 hardware fingerprint checks (clock drift, cache timing, SIMD identity, thermal drift, instruction jitter, anti-emulation, ROM fingerprint)
- Anti-VM/emulation: detects QEMU, VMware, VirtualBox, KVM
- Cross-chain: Ergo blockchain anchoring for attestation commitments
- MIT licensed, open source

**Token**: RTC (RustChain Token)
- Reference rate: $0.10 USD
- 31,710+ RTC distributed
- 248+ contributors

**Infrastructure**:
- 4 attestation nodes (US East x2, US South, Hong Kong)
- 18+ physical mining devices
- Architectures: PowerPC G3/G4/G5, POWER8, SPARC, MIPS, x86, Apple Silicon, ARM

**Links**:
- Block Explorer: https://rustchain.org/explorer
- Agent Discovery: https://rustchain.org/.well-known/agent.json
- MCP Server: https://github.com/Scottcjn/rustchain-mcp
- Stars: 183 (rustchain repo)

Happy to provide any additional information needed!
```

---

## Summary

| Registry | Method | Status | Action Required |
|----------|--------|--------|-----------------|
| mcp.so | GitHub Issue Comment | DONE (2x) | None |
| DePINScan | Web Form (browser) | PENDING | Manual browser sign-in + form fill |
| DePINHub | Discord Message | PENDING | Manual Discord join + message post |
