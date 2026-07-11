# =============================================================================
# Research Agent — Dockerfile
# Multi-stage build for production deployment
# =============================================================================

FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ────────────────────────────────────────────────────────
# Runtime stage
# ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system dependencies (for weasyprint/pdf generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/
COPY sandbox/ sandbox/
COPY docs/ docs/
COPY .env.example .env.example

# Create data directories (runtime volumes will override)
RUN mkdir -p /app/data/raw /app/data/processed /app/data/logs \
             /app/data/chroma_db /app/data/memories /app/data/lora_checkpoints \
             /app/reports/output /app/model_cache

# Expose ports: 8000 = FastAPI backend, 8080 = NiceGUI frontend
EXPOSE 8000 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
