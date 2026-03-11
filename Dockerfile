# RustChain Miner Dockerfile
# Note: Docker miners earn minimal rewards due to anti-VM detection in Proof-of-Antiquity
# For maximum rewards, run the miner on bare metal vintage hardware

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    dmidecode \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy miner files
COPY miners/linux/rustchain_linux_miner.py /app/miner.py
COPY miners/color_logs.py /app/color_logs.py

# Copy fingerprint checks if available
COPY miners/linux/fingerprint_checks.py /app/fingerprint_checks.py 2>/dev/null || true

# Install Python dependencies
RUN pip install --no-cache-dir requests

# Environment variables with defaults
ENV WALLET_NAME=""
ENV NODE_URL="https://rustchain.org"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f ${NODE_URL}/health || exit 1

# Run miner
# Note: Requires --privileged flag for hardware access (dmidecode)
CMD ["python", "-u", "miner.py"]
