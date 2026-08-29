# Metadata

## Primary title
RustChain’s VM Check: Why Physical Hardware Matters

## Alternate titles
- Proof of Antiquity Starts With Proving the Machine
- Why RustChain Attestation Exists Before the Multiplier

## Description
RustChain’s public API documents `/attest/submit` as the hardware-attestation gate used to validate a signed hardware fingerprint for epoch enrollment and to distinguish genuine physical hardware from a VM. This short explains why that identity step matters before any antiquity multiplier is meaningful.

Source: https://github.com/Scottcjn/Rustchain
API reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md

No claim is made that VM detection is infallible; the video sticks to the protocol behavior documented in the public API reference.

## Tags
RustChain, Proof of Antiquity, DePIN, hardware attestation, virtual machine, vintage computing, blockchain, PowerPC, physical hardware

## Suggested pinned comment
The key distinction here is protocol intent vs absolute security: RustChain documents attestation as the enrollment gate for signed hardware evidence. That is different from claiming any detector can never be bypassed.
