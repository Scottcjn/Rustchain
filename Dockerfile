FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt

COPY . .

ENV RUSTCHAIN_DB_PATH=/data/rustchain_v2.db \
    RC_ADMIN_KEY=change-me-in-env

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8099/health || exit 1

CMD ["python", "node/rustchain_v2_integrated_v2.2.1_rip200.py"]
