# RustChain Registry Submissions — Status & Priority

Prepared 2026-03-24. Ready-to-submit content for DePIN directories and MCP registries.

## Summary

| Registry | Type | Status | Priority | Effort | Blockers |
|----------|------|--------|----------|--------|----------|
| **mcp.so** | MCP Registry | Ready to submit | HIGH | 10 min | Logo needed |
| **Official MCP Registry** | MCP Registry | Needs PyPI publish first | HIGH | 1-2 hours | PyPI package + mcp-publisher CLI |
| **Smithery.ai** | MCP Registry | Needs Streamable HTTP or CLI | HIGH | 30 min - 2 hours | Account + possible HTTP wrapper |
| **Glama.ai** | MCP Registry | ALREADY INDEXED | LOW | 5 min | Just claim ownership |
| **DePINScan** | DePIN Directory | Ready to submit | MEDIUM | 15 min | Logo, no exchange listing |
| **DePINHub** | DePIN Directory | Ready (Discord msg) | MEDIUM | 10 min | Discord join required |

## Recommended Order of Action

1. **Glama.ai** — Claim the existing listing (5 min, already indexed)
2. **mcp.so** — Submit via their form or GitHub issue (10 min, lowest barrier)
3. **Smithery.ai** — Sign in and publish via URL or CLI (30 min)
4. **DePINScan** — Sign in and fill out project form (15 min)
5. **DePINHub** — Join Discord and send prepared message (10 min)
6. **Official MCP Registry** — Publish to PyPI first, then use mcp-publisher (1-2 hours)

## Files

- `depinscan_submission.md` — DePINScan project form fields and answers
- `depinhub_submission.md` — DePINHub Discord message (ready to paste)
- `smithery_submission.md` — Smithery.ai config files and CLI commands
- `mcp_so_submission.md` — mcp.so form fields and GitHub issue template
- `official_mcp_registry_submission.md` — Official registry with server.json and CLI steps
- `glama_status.md` — Already indexed, just needs claiming

## Common Description (for all submissions)

> RustChain is a DePIN blockchain that rewards real physical hardware through
> Proof-of-Antiquity (RIP-PoA). 7 hardware fingerprint checks verify authentic
> vintage and modern compute — G4 PowerBooks, SPARC workstations, POWER8 servers,
> and more. 4 attestation nodes, Ergo cross-chain anchoring, 24,884+ RTC
> distributed to 248+ contributors.

## Shared Blockers

- **Logo**: Multiple registries need a clean PNG/SVG logo. Create or locate one.
- **PyPI**: Official MCP Registry requires the package on PyPI.
- **Streamable HTTP**: Smithery prefers servers with HTTP transport (ours is stdio).
