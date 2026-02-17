# RustChain Node Dockerfile
FROM python:3.11-slim

LABEL maintainer="RustChain Community"
LABEL description="RustChain Proof-of-Antiquity Blockchain Node"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    RUSTCHAIN_HOME=/rustchain \
    RUSTCHAIN_DB=/rustchain/data/rustchain_v2.db \
    DOWNLOAD_DIR=/rustchain/downloads

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create rustchain directories
RUN mkdir -p ${RUSTCHAIN_HOME}/data ${DOWNLOAD_DIR} /app

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements-node.txt ./
RUN pip install --no-cache-dir -r requirements-node.txt

# Copy application code
COPY node/ ./node/
COPY tools/ ./tools/
COPY wallet/ ./wallet/
COPY *.py ./

# Copy Docker-specific files
COPY docker-entrypoint.py ./

# Copy additional resources
COPY README.md LICENSE ./

# Create a non-root user (security best practice)
RUN useradd -m -u 1000 rustchain && \
    chown -R rustchain:rustchain /app ${RUSTCHAIN_HOME}

USER rustchain

# Expose ports
# 8099: Dashboard HTTP
# 8088: API endpoint (if needed)
EXPOSE 8099 8088

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8099/health || exit 1

# Default command: run the dashboard with health check endpoint
CMD ["python3", "docker-entrypoint.py"]
