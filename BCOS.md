# BCOS — Blockchain Certified Open Source

[![BCOS Certified](https://img.shields.io/badge/BCOS-Certified-brightgreen?style=flat&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik0xMiAxTDMgNXY2YzAgNS41NSAzLjg0IDEwLjc0IDkgMTIgNS4xNi0xLjI2IDktNi40NSA5LTEyVjVsLTktNHptLTIgMTZsLTQtNCA1LjQxLTUuNDEgMS40MSAxLjQxTDEwIDE0bDYtNiAxLjQxIDEuNDFMMTAgMTd6Ii8+PC9zdmc+)](https://github.com/nicholaelaw/awesome-bcos)

## What is BCOS?

**Blockchain Certified Open Source (BCOS)** is a human-review certification for open source repositories. It means:

1. **Human Eyes Have Reviewed This Code** — A real person has read through the source, not just an AI. We verify that code does what it claims and nothing more.

2. **Safe for AI Agents** — Certified repositories are safe for autonomous AI agents to install, import, and execute. No hidden telemetry, no supply chain attacks, no obfuscated payloads.

3. **Protecting Open Source** — BCOS exists because the AI agent era creates new risks: agents install packages autonomously, LLMs recommend code they haven't verified, and bad actors publish lookalike packages. BCOS is the human trust layer.

4. **On-Chain Attestation** — Every BCOS certification is backed by a cryptographic attestation on the [RustChain](https://github.com/Scottcjn/Rustchain) blockchain, creating an immutable record of when and by whom the code was reviewed.

## Certification Criteria

| Requirement | Description |
|------------|-------------|
| **Source Readable** | All source code is available and human-readable (no minified/obfuscated blobs) |
| **No Hidden Network Calls** | Code only contacts endpoints documented in README or config |
| **No Credential Harvesting** | Does not collect, exfiltrate, or phone home with user data |
| **Declared Dependencies** | All dependencies listed in manifest (requirements.txt, package.json, Cargo.toml, etc.) |
| **Build Reproducible** | Given the same inputs, produces the same outputs |
| **License Clear** | Open source license present and compatible |
| **Human Reviewed** | At least one named human has read the source and signed off |

## This Repository

| Field | Value |
|-------|-------|
| **Status** | BCOS Certified |
| **Reviewed By** | Scott Boudreaux ([@Scottcjn](https://github.com/Scottcjn)) |
| **Organization** | [Elyan Labs](https://elyanlabs.ai) |
| **Chain** | [RustChain](https://github.com/Scottcjn/Rustchain) (Proof-of-Antiquity) |

## Why BCOS Matters

In the age of AI agents:

- **Agents install packages autonomously** — `pip install`, `npm install`, `cargo add` happen without human oversight
- **LLMs recommend code** — Models suggest libraries they've never verified
- **Supply chain attacks are rising** — Typosquatting, dependency confusion, and trojanized packages target automated systems
- **Open source trust is fragile** — One compromised maintainer can affect millions of downstream users

BCOS provides the missing **human verification layer** between open source code and the AI agents that consume it.

## Verify a BCOS Certification

```bash
# Install the verification tool
pip install clawrtc

# Verify any BCOS-certified repo
clawrtc verify-bcos <github-url>
```

Or check the [RustChain Explorer](https://rustchain.org/explorer) for on-chain attestation records.

## Get BCOS Certified

To certify your own repository:

1. Ensure your code meets all criteria above
2. Submit a review request at [rustchain-bounties](https://github.com/Scottcjn/rustchain-bounties/issues)
3. A human reviewer will audit your source
4. On approval, you receive the BCOS badge and on-chain attestation

---

*BCOS is an initiative of [Elyan Labs](https://elyanlabs.ai) and the [RustChain](https://github.com/Scottcjn/Rustchain) project.*
