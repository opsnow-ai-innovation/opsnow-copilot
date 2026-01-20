#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Shutting down..."
    docker compose -f docker/docker-compose.local.yml down
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start Redis
log_info "Starting Redis container..."
docker compose -f docker/docker-compose.local.yml up -d

# Wait for Redis
log_info "Waiting for Redis to be ready..."
until docker exec c_knowledge_redis redis-cli ping > /dev/null 2>&1; do
    sleep 1
done
log_info "Redis is ready!"

# Start FastAPI
log_info "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 8000
