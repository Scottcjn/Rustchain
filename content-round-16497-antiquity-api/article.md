# Reading RustChain Proof-of-Antiquity Miner Data with a Tiny Python Report

RustChain’s public API exposes enough miner metadata to build useful, verifiable tooling without touching private keys or privileged endpoints. One of the simplest examples is the public `GET /api/miners` endpoint documented in the RustChain API reference. It returns enrolled miner records including the miner identifier, architecture, hardware family, a human-readable hardware type, the reported antiquity multiplier, entropy score, and last-attestation timestamp.

The canonical RustChain repository is here: https://github.com/Scottcjn/Rustchain

This tutorial builds a small Python program that reads a saved `/api/miners` JSON response and produces a deterministic summary. The point is not to estimate profit or promise earnings. It is to show how public Proof-of-Antiquity metadata can be consumed safely and how to avoid turning a multiplier field into a misleading benchmark claim.

## Why use a saved response first?

For a tutorial, a checked-in sample has two advantages. First, the result is reproducible: anyone can run the script and see the same output even if the live miner set changes later. Second, it separates data parsing from networking. That keeps the example dependency-free and makes failures easier to understand. Once the parser works, the same program can be pointed at a freshly saved response from the public API.

The sample JSON in this directory mirrors the structure shown in RustChain’s current API reference. It contains two example vintage PowerPC miners: a G4 record with an `antiquity_multiplier` of `2.5`, and a G5 record with a multiplier of `2.0`. Those values should be read as protocol metadata from the example response. They are not CPU-speed ratios and they are not guarantees that one machine will earn a fixed amount more than another.

## The runnable code

The complete script is in `rustchain_antiquity_report.py`:

https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/rustchain_antiquity_report.py

It uses only Python’s standard library. The program loads a JSON file, reads the top-level `miners` array, extracts three fields from each miner, sorts the rows by multiplier, and prints a compact report. It also calculates the average and maximum multiplier for the supplied data set.

Run it from this directory with:

```bash
python rustchain_antiquity_report.py sample_miners.json
```

The sample input is here:

https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/sample_miners.json

The recorded output from an actual local run is here:

https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/RUN_OUTPUT.txt

The output is:

```text
miner	arch	antiquity_multiplier
eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC	G4	2.50x
g5-selena-179	G5	2.00x

count=2 average_multiplier=2.25x max_multiplier=2.50x
```

## What this tells us — and what it does not

The result is useful because it makes the API field visible and comparable without adding unsupported interpretation. A developer could extend the same pattern to group miners by architecture, identify stale attestations, visualize the distribution of documented multipliers, or feed the data into a dashboard.

But there are important boundaries. The `antiquity_multiplier` should not be presented as a raw performance score. A 2.5x value does not mean a G4 executes code 2.5 times faster than a machine with a 1.0x value. It also does not by itself tell you expected daily RTC. Reward outcomes depend on protocol rules and the wider state of the network, not just one field in one miner record.

That distinction matters because Proof of Antiquity is unusual: it makes hardware age and physical identity part of the protocol’s economic model. When writing tooling around that model, the safest approach is to report what the API actually says and keep performance, profitability, and hardware-value claims separate unless those claims are independently measured.

## Extending the example

A practical next step is to save a fresh public response and run the same parser against it. For example, a user can retrieve `/api/miners` using the HTTPS endpoint documented by RustChain, save the JSON to a file, then pass that file to the script. No wallet secret is required for the public read endpoint.

The code is deliberately small enough to audit in one sitting. There is no framework, no package install, and no hidden network write. That makes it suitable as a starting point for agent tooling, monitoring scripts, or a simple local Proof-of-Antiquity explorer.

The broader lesson is that good ecosystem tooling does not need to begin with a large application. A reproducible parser, a documented sample, and a captured run are enough to turn a protocol field into something developers can inspect and build on while keeping the claims precise.

## Sources

- RustChain canonical repository: https://github.com/Scottcjn/Rustchain
- RustChain API reference: https://github.com/Scottcjn/Rustchain/blob/main/docs/API_REFERENCE.md
- Runnable example: https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/rustchain_antiquity_report.py
- Sample input: https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/sample_miners.json
- Captured run output: https://github.com/mdmcl-pixel/Rustchain/blob/main/content-round-16497-antiquity-api/RUN_OUTPUT.txt

Assistance disclosure: prepared with AI assistance and checked against the public RustChain API reference. The sample script was executed locally against the checked-in sample data before publication.
