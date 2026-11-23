# Multi-Stage Dockerfile for TraceOps AI (Standalone Cloud Run Engine)
# Serves high-performance FastAPI proxy directly on $PORT (Default: 8080)
# Target architecture: linux/amd64

FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Final lightweight runner image
FROM python:3.11-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TRACEOPS_MODE=enforce

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed site-packages and binaries
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY traceops/ /app/traceops/
COPY pyproject.toml /app/

# Non-root user for security best practices
RUN useradd -m -u 1001 traceopsuser && \
    chown -R traceopsuser:traceopsuser /app
USER traceopsuser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Launch production FastAPI proxy on $PORT via uvicorn
CMD ["sh", "-c", "uvicorn traceops.api:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2"]
