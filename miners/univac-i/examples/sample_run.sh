#!/bin/bash
#
# Example: Run UNIVAC I Miner
#

set -e

echo "========================================"
echo "UNIVAC I Miner - Example Run"
echo "========================================"
echo ""

# Check if built
if [ ! -f "./build/miner_tape.tap" ]; then
    echo "Building miner first..."
    ./build.sh
fi

echo ""
echo "Configuration:"
echo "  Wallet: RTC4325af95d26d59c3ef025963656d22af638bb96b"
echo "  Node:   https://50.28.86.131"
echo "  Mode:   SIMH Simulator (emulator)"
echo ""
echo "Note: Running in emulator = 0 RTC rewards"
echo "      Real UNIVAC I hardware required for bounty"
echo ""
echo "========================================"
echo "Starting Miner..."
echo "========================================"
echo ""

# Run in simulator
./run_simulator.sh

echo ""
echo "========================================"
echo "Example Complete"
echo "========================================"
echo ""
echo "To run on real UNIVAC I hardware:"
echo "  1. Load build/miner_tape.tap onto magnetic tape"
echo "  2. Mount tape on UNIVAC I tape unit"
echo "  3. On UNISCOPE console:"
echo "     LOAD TAPE UNIT 1"
echo "     EXECUTE MINER"
echo "     ENTER WALLET: RTC4325af95d26d59c3ef025963656d22af638bb96b"
echo ""
echo "Good luck mining on history's first commercial computer! 🎉"
echo ""
