#!/bin/bash
#
# Build script for UNIVAC I Miner
# 
# This script assembles the UNIVAC I miner source code.
# Requires: UNIVAC I assembler or SIMH cross-assembler
#

set -e

echo "========================================"
echo "RustChain Miner for UNIVAC I"
echo "Build Script v0.1.0"
echo "========================================"
echo ""

# Configuration
UNASSEMBLER="${UNASSEMBLER:-unassembler}"  # UNIVAC I assembler
OUTPUT_DIR="./build"
SRC_DIR="./src"

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo "[1/5] Checking assembler..."
if command -v "$UNASSEMBLER" &> /dev/null; then
    echo "      Found: $UNASSEMBLER"
else
    echo "      Warning: $UNASSEMBLER not found"
    echo "      Install SIMH or UNIVAC I assembler"
    echo "      sudo apt install simh  # Linux"
    echo "      brew install simh      # macOS"
    echo ""
    echo "      Falling back to cross-assembly mode..."
    UNASSEMBLER="simh-unassembler"
fi

echo ""
echo "[2/5] Assembling miner_main.s..."
"$UNASSEMBLER" "$SRC_DIR/miner_main.s" -o "$OUTPUT_DIR/miner_main.bin"
echo "      Output: $OUTPUT_DIR/miner_main.bin"

echo ""
echo "[3/5] Assembling hw_univac.s..."
"$UNASSEMBLER" "$SRC_DIR/hw_univac.s" -o "$OUTPUT_DIR/hw_univac.bin"
echo "      Output: $OUTPUT_DIR/hw_univac.bin"

echo ""
echo "[4/5] Assembling network.s..."
"$UNASSEMBLER" "$SRC_DIR/network.s" -o "$OUTPUT_DIR/network.bin"
echo "      Output: $OUTPUT_DIR/network.bin"

echo ""
echo "[5/5] Creating magnetic tape image..."
# Combine all binaries into tape image
cat "$OUTPUT_DIR/miner_main.bin" \
    "$OUTPUT_DIR/hw_univac.bin" \
    "$OUTPUT_DIR/network.bin" \
    > "$OUTPUT_DIR/miner_tape.tap"

echo "      Output: $OUTPUT_DIR/miner_tape.tap"

echo ""
echo "========================================"
echo "Build Complete!"
echo "========================================"
echo ""
echo "Output files:"
echo "  - $OUTPUT_DIR/miner_main.bin    (Main program)"
echo "  - $OUTPUT_DIR/hw_univac.bin     (Hardware detection)"
echo "  - $OUTPUT_DIR/network.bin       (Network stack)"
echo "  - $OUTPUT_DIR/miner_tape.tap    (Combined tape image)"
echo ""
echo "To run in SIMH simulator:"
echo "  ./run_simulator.sh"
echo ""
echo "To run on real UNIVAC I hardware:"
echo "  1. Load miner_tape.tap onto magnetic tape"
echo "  2. Mount tape on UNIVAC I tape unit"
echo "  3. Execute: LOAD TAPE UNIT 1"
echo "  4. Execute: EXECUTE MINER"
echo ""
echo "Note: Real UNIVAC I hardware required for bounty rewards."
echo "      Emulator mining earns 0 RTC."
echo ""
