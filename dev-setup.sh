#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────────────────────────
# RustChain Development Stack - One-command setup
# ────────────────────────────────────────────────────────────────

COMPOSE_FILE="docker-compose.dev.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.dev.example"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { printf "${GREEN}[+]${NC} %s\n" "$*"; }
warn()  { printf "${YELLOW}[!]${NC} %s\n" "$*"; }
error() { printf "${RED}[x]${NC} %s\n" "$*"; exit 1; }

# ── Pre-flight checks ────────────────────────────────────────────
command -v docker  >/dev/null 2>&1 || error "docker is not installed."
command -v docker  >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || error "docker compose v2 plugin is required."

info "RustChain Dev Stack Setup"
echo "─────────────────────────────────────────────"

# ── Env file ──────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_EXAMPLE" ]; then
        cp "$ENV_EXAMPLE" "$ENV_FILE"
        info "Created $ENV_FILE from $ENV_EXAMPLE"
    else
        warn "No $ENV_EXAMPLE found, continuing without .env"
    fi
else
    info "$ENV_FILE already exists, skipping copy"
fi

# ── Pull / Build ─────────────────────────────────────────────────
info "Pulling base images..."
docker compose -f "$COMPOSE_FILE" pull --ignore-buildable 2>/dev/null || true

info "Building project images..."
docker compose -f "$COMPOSE_FILE" build

# ── Launch ────────────────────────────────────────────────────────
info "Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── Wait for health ──────────────────────────────────────────────
info "Waiting for RustChain node to become healthy..."
ATTEMPTS=0
MAX_ATTEMPTS=30
until docker inspect --format='{{.State.Health.Status}}' rc-dev-node 2>/dev/null | grep -q "healthy"; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
        warn "Node did not become healthy within ${MAX_ATTEMPTS}0s. Check logs: docker compose -f $COMPOSE_FILE logs rustchain-node"
        break
    fi
    sleep 10
done

if [ "$ATTEMPTS" -lt "$MAX_ATTEMPTS" ]; then
    info "Node is healthy!"
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────────"
info "RustChain Dev Stack is running"
echo ""
echo "  Node dashboard   http://localhost:${NODE_PORT:-8099}"
echo "  MongoDB          mongodb://localhost:${MONGO_PORT:-27017}/rustchain"
echo "  Redis            redis://localhost:${REDIS_PORT:-6379}"
echo "  Prometheus       http://localhost:${PROMETHEUS_PORT:-9090}"
echo "  Grafana          http://localhost:${GRAFANA_PORT:-3000}  (admin / rustchain)"
echo ""
echo "  Logs:   docker compose -f $COMPOSE_FILE logs -f"
echo "  Stop:   docker compose -f $COMPOSE_FILE down"
echo "  Reset:  docker compose -f $COMPOSE_FILE down -v"
echo "─────────────────────────────────────────────"
