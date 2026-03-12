#!/bin/bash
# Run Epoch Determinism Simulator self-tests
# Usage: ./run_tests.sh [--verbose] [--ci]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERBOSE=""
CI_MODE=""

if [[ "$1" == "--verbose" ]] || [[ "$1" == "-v" ]]; then
    VERBOSE="-v"
fi

if [[ "$1" == "--ci" ]]; then
    CI_MODE="--tb=short"
    VERBOSE="-v"
fi

echo "========================================"
echo "Epoch Determinism Simulator Self-Tests"
echo "========================================"
echo

# Check Python version
echo "Python version:"
python3 --version
echo

# Run unit tests
echo "Running unit tests..."
python3 -m pytest tests/test_epoch_simulator.py $VERBOSE $CI_MODE
echo

# Run integration tests
echo "Running integration tests..."
python3 -m pytest tests/test_cross_node_replay.py $VERBOSE $CI_MODE
echo

# Run determinism verification
echo "Running determinism verification..."
python3 src/cross_node_replay.py --record --seed 42 --epochs 2 --output /tmp/test_replay.json
python3 src/cross_node_replay.py --verify /tmp/test_replay.json --ci
echo

# Cleanup
rm -f /tmp/test_replay.json

echo "========================================"
echo "All tests passed!"
echo "========================================"
