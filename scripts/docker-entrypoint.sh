#!/bin/bash
# =============================================================================
# Research Agent — Docker Entrypoint
#
# Starts both backend (FastAPI) and frontend (NiceGUI) in a single container.
# The backend runs in the background; the frontend runs in the foreground
# so container lifecycle follows the UI process.
# =============================================================================

set -e

echo "=== Research Agent — Starting Services ==="
echo "  Environment: ${APP_ENV:-development}"
echo "  Backend:     http://0.0.0.0:8000"
echo "  API Docs:    http://0.0.0.0:8000/docs"
echo "  Frontend:    http://0.0.0.0:8080"
echo ""

# ── Step 1: Apply database migrations ──
echo "[1/3] Applying database migrations..."
cd /app
python -m alembic upgrade head 2>/dev/null || \
    echo "  (Alembic not initialized or no migrations — skipping)"

# ── Step 2: Start backend API in background ──
echo "[2/3] Starting backend API (uvicorn, port 8000)..."
uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --workers 1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# ── Step 3: Start frontend (foreground) ──
echo "[3/3] Starting frontend (NiceGUI, port 8080)..."
echo ""
echo "=== Research Agent is running ==="
echo "  Open http://localhost:8080 in your browser"
echo ""
exec python -m frontend.app
