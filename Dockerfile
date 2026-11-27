# Multi-Stage Hardened Dockerfile for TraceOps AI (Cloud Run Ready)
# Serves Streamlit Control Room HUD on $PORT (8080) with background FastAPI proxy on 8000
# Target architecture: linux/amd64

FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-deps .

# Final lightweight non-root runner image
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TRACEOPS_ENV=production \
    TRACEOPS_MODE=enforce

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY traceops/ /app/traceops/
COPY dashboard/ /app/dashboard/
COPY start.sh pyproject.toml ./

RUN chmod +x /app/start.sh && \
    useradd -m -u 1001 -s /usr/sbin/nologin traceopsuser && \
    chown -R traceopsuser:traceopsuser /app

USER traceopsuser

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8080/_stcore/health || exit 1

CMD ["/bin/bash", "/app/start.sh"]
