# Bounty Contribution

This addresses issue #933: Add IBM PC/XT DOS Miner (Bounty #422)

## Description
## Summary
This PR implements a complete DOS-compatible miner for IBM PC/XT systems with 8088 CPU.

## Changes
- Added miners/dos-xt/ directory with full DOS miner implementation
- Uses PIT timer for timing and DOS interrupts for hardware access
- Implements Rustchain stratum protocol over packet driver (NE2000 compatible)
- Includes build scripts and comprehensive documentation

## Files Added
- miners/dos-xt/main.c - Main entry point and miner loop
- miners/dos-xt/hw_xt.c/h - IBM PC/XT hardwar

## Payment
0x4F666e7b4F63637223625FD4e9Ace6055fD6a847
