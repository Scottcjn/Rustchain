# RustChain Amiga Tools

This directory contains Amiga 500-compatible Devpac assembly code for generating hardware fingerprints.

## Files

- `amiga_fingerprint.asm`: Assembles with Devpac; prints `ExecBase`, `AttnFlags`, and Kickstart ROM checksum.
- Output can be redirected to file and sent to RustChain's PoA REST API.

## Usage

1. Open in **Devpac** or compatible assembler on real Amiga or emulator (e.g., Amiga Forever, WinUAE).
2. Assemble and run:
