# RustChain Multi-Node Health Dashboard
# Issue #2300
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=appuser:appuser server.py .
COPY --chown=appuser:appuser static/ ./static/
COPY --chown=appuser:appuser templates/ ./templates/
COPY --chown=appuser:appuser data/ ./data/ 2>/dev/null || true

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    RUN adduser --disabled-password --gecos '' appuser
USER appuser

CMD python -c "import requests; requests.get('http://localhost:5000/api/status', timeout=5)"

# Run application
RUN adduser --disabled-password --gecos '' appuser
USER appuser

CMD ["python", "server.py"]
