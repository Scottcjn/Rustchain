# RustChain Multi-Node Health Dashboard
# Issue #2300
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY health-dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared liveness probe (imported as monitoring.node_probe)
COPY monitoring/__init__.py monitoring/node_probe.py ./monitoring/

# Copy application files. The dashboard renders its page from render_template_string,
# so it has no static/ or templates/ directory to ship.
COPY health-dashboard/server.py .

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/status', timeout=5)"

# Run application
CMD ["python", "server.py"]
