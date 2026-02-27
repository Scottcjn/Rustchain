#\!/bin/sh
# RustChain G5 Miner - Shell Script for Python 2.5 compatibility
# Power Mac G5 Dual 2GHz - 2.0x Antiquity Bonus

WALLET="ppc_g5_130_$(hostname | md5)RTC"
RIP_URL="https://50.28.86.131"

echo "=== RustChain G5 Miner ==="
echo "Wallet: $WALLET"
echo "Architecture: PowerPC G5 (2.0x bonus)"

while true; do
    echo ""
    echo "=== Generating Entropy at $(date) ==="
    
    # Collect timing samples using time command
    SAMPLES=""
    for i in $(seq 1 100); do
        START=$(perl -e "print time()")
        x=1
        for j in $(seq 1 50); do x=$((x + j)); done
        END=$(perl -e "print time()")
        SAMPLES="$SAMPLES$((END - START)),"
    done
    
    # Generate entropy hash
    ENTROPY=$(echo "$SAMPLES$(date +%s)" | md5)
    TIMESTAMP=$(date +%s)000
    
    echo "Entropy Hash: $ENTROPY"
    echo "Submitting to RIP service..."
    
    # Get challenge
    CHALLENGE=$(curl -s -X POST "$RIP_URL/attest/challenge" -H "Content-Type: application/json" 2>/dev/null)
    NONCE=$(echo "$CHALLENGE" | sed -n "s/.*nonce.*:\s*\"\([^\"]*\)\".*/\1/p")
    
    if [ -n "$NONCE" ]; then
        # Submit attestation
        RESULT=$(curl -s -X POST "$RIP_URL/attest/submit" \
            -H "Content-Type: application/json" \
            -d "{\"miner\":\"$WALLET\",\"report\":{\"nonce\":\"$NONCE\"},\"device\":{\"hostname\":\"$(hostname)\",\"arch\":\"G5\",\"family\":\"PowerPC G5\",\"os\":\"Darwin 9.8.0\"},\"signals\":{\"entropy_hash\":\"$ENTROPY\",\"sample_count\":100}}" 2>/dev/null)
        echo "Result: $RESULT"
    else
        echo "Failed to get challenge"
    fi
    
    echo "Sleeping 600 seconds..."
    sleep 600
done
