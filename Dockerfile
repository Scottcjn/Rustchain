FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY node/requirements.txt* /app/
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r requirements-miner.txt || pip install --no-cache-dir flask nacl prometheus-client

# Copy RustChain node files
COPY node/ /app/node/
COPY rustchain_v2.db /app/ 2>/dev/null || true

# Create data directory for SQLite persistence
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=node/rustchain_v2_integrated_v2.2.1_rip200.py
ENV FLASK_ENV=production
ENV RUSTCHAIN_DB_PATH=/app/data/rustchain_v2.db

# Expose Flask port
EXPOSE 8099

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8099/api/stats', timeout=5)" || exit 1

# Run the RustChain node
CMD ["gunicorn", "--bind", "0.0.0.0:8099", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "node.rustchain_v2_integrated_v2.2.1_rip200:app"]
