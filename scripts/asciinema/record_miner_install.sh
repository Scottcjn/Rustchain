#!/bin/bash
# =============================================================================
# RustChain Miner Installation - Asciinema Recording Script
# =============================================================================
# This script records the complete miner installation process for documentation.
# 
# Prerequisites:
#   - asciinema installed: brew install asciinema (macOS) or pip install asciinema
#   - RustChain repository cloned
#   - Python 3.x installed
#
# Usage:
#   ./record_miner_install.sh
#
# Output:
#   docs/asciinema/miner_install.cast
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$PROJECT_ROOT/docs/asciinema"
OUTPUT_FILE="$OUTPUT_DIR/miner_install.cast"

# Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

echo "🎬 RustChain Miner Installation Recording Script"
echo "=================================================="
echo ""
echo "This script will guide you through recording the miner installation process."
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

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi
echo "✅ Python 3 installed: $(python3 --version)"

echo ""
echo "Recording steps:"
echo "----------------"
echo "1. Clone the repository (if not already done)"
echo "2. Create virtual environment"
echo "3. Install dependencies"
echo "4. Configure environment"
echo "5. Start the miner"
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

echo "🧱 RustChain Miner Installation"
echo "================================"
echo ""

# Step 1: Clone repository
echo "📦 Step 1: Cloning RustChain repository..."
if [ ! -d "Rustchain" ]; then
    git clone https://github.com/Scottcjn/Rustchain.git
fi
cd Rustchain

# Step 2: Create virtual environment
echo ""
echo "🐍 Step 2: Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Step 3: Install dependencies
echo ""
echo "📥 Step 3: Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Step 4: Configure environment
echo ""
echo "⚙️  Step 4: Configuring environment..."
cp .env.example .env
echo "WALLET_ADDRESS=RTC1YourWalletAddress001" >> .env

# Step 5: Verify installation
echo ""
echo "✅ Step 5: Verifying installation..."
python -c "import rustchain; print('RustChain installed successfully!')"

echo ""
echo "🎉 Installation complete!"
echo "Run 'python miners/rustchain_miner.py' to start mining"
RECORDING_SCRIPT

# Record the installation process
asciinema rec --title "RustChain Miner Installation" \
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
echo "To convert to GIF (requires svg-term or asciinema-agg):"
echo "  asciinema agg $OUTPUT_FILE --out $OUTPUT_DIR/miner_install.gif"
echo ""
echo "To embed in documentation, see: docs/INSTALLATION_WALKTHROUGH.md"
