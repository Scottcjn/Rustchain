# Dockerfile for RustChain Prometheus Exporter - Bounty #765
#
# Usage:
#   docker build -t rustchain-exporter:latest .
#   docker run -p 9100:9100 rustchain-exporter:latest

FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY rustchain_exporter.py .
COPY metrics_exposition.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash exporter \
    && chown -R exporter:exporter /app

USER exporter

# Expose the exporter port
EXPOSE 9100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9100/health || exit 1

# Run the exporter
ENTRYPOINT ["python", "rustchain_exporter.py"]
CMD ["--port", "9100"]
