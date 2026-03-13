#!/bin/bash
# =============================================================================
# RustChain First Attestation - Asciinema Recording Script
# =============================================================================
# This script records the first attestation process for documentation.
# 
# Prerequisites:
#   - asciinema installed
#   - RustChain miner installed and configured
#   - Wallet address configured
#
# Usage:
#   ./record_first_attestation.sh
#
# Output:
#   docs/asciinema/first_attestation.cast
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/docs/asciinema"
OUTPUT_FILE="$OUTPUT_DIR/first_attestation.cast"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "🎬 RustChain First Attestation Recording Script"
echo "================================================"
echo ""
echo "This script will guide you through recording the first attestation process."
echo ""
echo "Prerequisites check:"
echo "-------------------"

# Check if asciinema is installed
if ! command -v asciinema &> /dev/null; then
    echo "❌ asciinema not found. Install with:"
    echo "   macOS: brew install asciinema"
    echo "   Linux: pip install asciinema"
    exit 1
fi
echo "✅ asciinema installed: $(asciinema --version)"

echo ""
echo "Recording steps:"
echo "----------------"
echo "1. Start the miner"
echo "2. View attestation challenge"
echo "3. Submit hardware fingerprint"
echo "4. Receive attestation result"
echo "5. View mining rewards"
echo ""
echo "Press Ctrl+C at any time to abort."
echo "Press Enter to start recording..."
read -r

# Start the asciinema recording
echo "🔴 Recording started: $OUTPUT_FILE"
echo ""

# Create a temporary script to record
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << 'RECORDING_SCRIPT'
#!/bin/bash
# This is the script that will be recorded

echo "🧱 RustChain First Attestation"
echo "=============================="
echo ""

# Step 1: Start the miner
echo "🚀 Step 1: Starting RustChain miner..."
cd Rustchain
source venv/bin/activate
python miners/rustchain_miner.py &
MINER_PID=$!
sleep 2

# Step 2: View attestation challenge
echo ""
echo "📋 Step 2: Viewing attestation challenge..."
curl -s http://localhost:5000/api/attestation/challenge | jq .

# Step 3: Submit hardware fingerprint
echo ""
echo "🔍 Step 3: Submitting hardware fingerprint..."
python scripts/submit_attestation.py --wallet RTC1YourWalletAddress001

# Step 4: Receive attestation result
echo ""
echo "📬 Step 4: Receiving attestation result..."
curl -s http://localhost:5000/api/attestation/status | jq .

# Step 5: View mining rewards
echo ""
echo "💰 Step 5: Viewing mining rewards..."
curl -s http://localhost:5000/api/rewards/balance?wallet=RTC1YourWalletAddress001 | jq .

# Stop the miner
kill $MINER_PID 2>/dev/null || true

echo ""
echo "🎉 First attestation complete!"
echo "Your miner is now part of the RustChain network!"
RECORDING_SCRIPT

# Record the attestation process
asciinema rec --title "RustChain First Attestation" \
    --command "bash $TEMP_SCRIPT" \
    "$OUTPUT_FILE"

# Cleanup
rm -f "$TEMP_SCRIPT"

echo ""
echo "✅ Recording saved to: $OUTPUT_FILE"
echo ""
echo "To play back the recording:"
echo "  asciinema play $OUTPUT_FILE"
echo ""
echo "To convert to GIF:"
echo "  asciinema agg $OUTPUT_FILE --out $OUTPUT_DIR/first_attestation.gif"
echo ""
echo "To embed in documentation, see: docs/INSTALLATION_WALKTHROUGH.md"
