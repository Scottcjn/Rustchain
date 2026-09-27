# Metadata

## Primary title
Signed ≠ Settled: RustChain’s Ed25519 Transfer Flow

## Alternate titles
- RustChain Wallet Transfers Without an Admin Key
- What `phase: pending` Really Means on RustChain

## Hook
“A RustChain wallet transfer can be signed without an admin key.”

## Description
A short, source-grounded look at RustChain’s documented `/wallet/transfer/signed` flow: Ed25519 authorization, the `verified: true` response, and why `phase: pending` still matters before confirmation.

Canonical repo: https://github.com/Scottcjn/Rustchain
API reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

## Tags
RustChain, Ed25519, blockchain, wallet, cryptography, settlement, signed transfer, DePIN

## On-screen disclaimer
Educational architecture explainer. Never expose private keys or signing secrets.