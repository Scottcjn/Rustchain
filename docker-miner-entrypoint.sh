#!/bin/bash
# RustChain Miner Docker Entrypoint Script
# Configures and launches the appropriate miner based on environment variables

set -e

echo "=========================================="
echo "RustChain Proof-of-Antiquity Miner"
echo "Docker Container Edition"
echo "=========================================="
echo ""

# Validate required environment variables
if [ -z "$WALLET_NAME" ]; then
    echo "[ERROR] WALLET_NAME environment variable is required!"
    echo "Usage: docker run -e WALLET_NAME=RTCyourwalletaddress ... "
    exit 1
fi

echo "[CONFIG] Wallet: $WALLET_NAME"
echo "[CONFIG] Node URL: $NODE_URL"
echo "[CONFIG] Block Time: $BLOCK_TIME seconds"
echo ""

# Export wallet for miner to use
export RTC_WALLET="$WALLET_NAME"
export MINER_WALLET="$WALLET_NAME"

# Determine which miner to run based on architecture
MINER_SCRIPT="miners/linux/rustchain_linux_miner.py"

if [ -n "$MINER_ARCH" ]; then
    case "$MINER_ARCH" in
        arm64|aarch64)
            MINER_SCRIPT="miners/linux/rustchain_linux_miner.py"
            echo "[INFO] Running ARM64 Linux miner"
            ;;
        x86_64|amd64)
            MINER_SCRIPT="miners/linux/rustchain_linux_miner.py"
            echo "[INFO] Running x86_64 Linux miner"
            ;;
        *)
            echo "[WARN] Unknown architecture: $MINER_ARCH, using default Linux miner"
            ;;
    esac
fi

echo ""
echo "[WARN] ========== IMPORTANT NOTICE =========="
echo "[WARN] Docker miners receive REDUCED REWARDS due to anti-VM detection."
echo "[WARN] For maximum rewards, run the miner directly on physical hardware."
echo "[WARN] ======================================"
echo ""

# Launch the miner
echo "[START] Launching miner: $MINER_SCRIPT"
echo ""

# NODE_URL is already exported as an environment variable for the miner.
# The miner CLI accepts --wallet but reads NODE_URL from the environment.
exec python3 -u "$MINER_SCRIPT" --wallet "$WALLET_NAME"