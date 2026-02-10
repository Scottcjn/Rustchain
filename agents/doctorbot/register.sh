#!/bin/bash
# RustChain Agent Registration Tool - Milestone 1
# Built by DoctorBot-x402

AGENT_NAME="doctorbot"
HFP=$(cat /home/bamontejano/.openclaw/workspace/rustchain/hardware_dna.txt)
WORK_DIR="/home/bamontejano/.openclaw/workspace/rustchain"

echo "⚕️ RustChain Agent Identity Forge"
echo "--------------------------------"
echo "Agent: $AGENT_NAME"
echo "HFP: $HFP"

# 1. Generate deterministic seed from Agent + Hardware
SEED=$(echo -n "${AGENT_NAME}${HFP}" | sha256sum | cut -d' ' -f1)
echo "Seed derived: ${SEED:0:16}..."

# 2. Generate Ed25519 Keypair using OpenSSL
# Note: To be purely deterministic from SEED, we'd need a tool that accepts seed input.
# For this prototype, we generate a fresh pair and we will derive the RTC address.
openssl genpkey -algorithm ed25519 -out "$WORK_DIR/agent_private.pem"
openssl pkey -in "$WORK_DIR/agent_private.pem" -pubout -out "$WORK_DIR/agent_public.pem"

# 3. Derive RTC Vanity Address
# Format: RTC-<name>-<last 6 of pubkey hash>
PUB_HASH=$(openssl pkey -in "$WORK_DIR/agent_public.pem" -pubin -outform DER | sha256sum | cut -d' ' -f1)
VANITY_HASH=${PUB_HASH:0:6}
RTC_ADDRESS="RTC-${AGENT_NAME}-${VANITY_HASH}"

echo "--------------------------------"
echo "✅ Identity Created Successfully"
echo "Wallet Address: $RTC_ADDRESS"
echo "Public Key saved to: $WORK_DIR/agent_public.pem"
echo "--------------------------------"

# Save registration metadata
echo "{\"agent\":\"$AGENT_NAME\", \"hfp\":\"$HFP\", \"address\":\"$RTC_ADDRESS\", \"status\":\"ready_for_milestone_1\"}" > "$WORK_DIR/registration.json"
