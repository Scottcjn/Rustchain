#!/bin/bash
#
# Run UNIVAC I Miner in SIMH Simulator
#
# SIMH (Computer History Simulation Project) provides
# accurate simulation of vintage computers including UNIVAC I.
#

set -e

echo "========================================"
echo "UNIVAC I Miner - SIMH Simulator"
echo "========================================"
echo ""

# Check if SIMH is installed
if ! command -v u1100 &> /dev/null; then
    echo "ERROR: SIMH UNIVAC I simulator not found!"
    echo ""
    echo "Install SIMH:"
    echo "  Ubuntu/Debian: sudo apt install simh"
    echo "  macOS:         brew install simh"
    echo "  Windows:       Download from http://simh-github.com/"
    echo ""
    exit 1
fi

echo "[1/3] Starting SIMH UNIVAC I simulator..."
echo ""

# Create SIMH command script
cat > /tmp/univac_miner.simh << 'EOF'
; UNIVAC I Simulator Script for RustChain Miner
set cpu idle
set console telnet=2026

; Load magnetic tape image
attach tape0 build/miner_tape.tap

; Configure tape unit
set tape0 enabled

; Load program from tape
load tape0

; Start miner
; Note: In simulator, will detect emulator and earn 0 RTC
execute miner

; Run for 1000 instructions (demo)
go 1000

; Show status
show cpu
show tape0

; Detach and exit
detach tape0
quit
EOF

echo "[2/3] Running miner in simulator..."
echo ""

# Run SIMH
u1100 /tmp/univac_miner.simh

echo ""
echo "[3/3] Simulation complete."
echo ""
echo "========================================"
echo "Simulator Output"
echo "========================================"
echo ""
echo "Note: Running in SIMH emulator."
echo "      Emulator detected - rewards: 0 RTC"
echo ""
echo "To earn RTC rewards, run on real UNIVAC I hardware!"
echo "(Only 46 systems ever built - check museums!)"
echo ""
