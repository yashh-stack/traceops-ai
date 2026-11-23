#!/usr/bin/env bash
# TraceOps AI Single-Container Entrypoint
# Boots FastAPI on 127.0.0.1:8000 in background, waits for health check,
# and starts Streamlit public dashboard on ${PORT:-8080}

set -euo pipefail

echo "=========================================================="
echo "⚡ Starting TraceOps AI Engine & Jury Dashboard"
echo "=========================================================="

# 1. Start FastAPI proxy daemon in background
echo "[1/3] Starting FastAPI proxy on 127.0.0.1:8000..."
uvicorn traceops.api:app --host 127.0.0.1 --port 8000 --workers 1 &
FASTAPI_PID=$!

# 2. Wait for FastAPI health endpoint
echo "[2/3] Waiting for FastAPI proxy to be healthy..."
for i in {1..30}; do
    if curl -s -f "http://127.0.0.1:8000/health" > /dev/null 2>&1; then
        echo "✅ FastAPI Proxy is healthy on 127.0.0.1:8000"
        break
    fi
    sleep 0.5
done

# 3. Exec Streamlit on Cloud Run public port
PORT="${PORT:-8080}"
echo "[3/3] Launching Streamlit Jury Control Room on port ${PORT}..."
exec streamlit run dashboard/app.py \
    --server.port "${PORT}" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
