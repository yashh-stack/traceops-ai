# Multi-Stage Dockerfile for TraceOps AI (Streamlit Control Room + FastAPI Proxy)
# Serves interactive Streamlit HUD on $PORT (Default: 8080) with background FastAPI proxy
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
COPY dashboard/ /app/dashboard/
COPY start.sh /app/start.sh
COPY pyproject.toml /app/

RUN chmod +x /app/start.sh

# Non-root user for security best practices
RUN useradd -m -u 1001 traceopsuser && \
    chown -R traceopsuser:traceopsuser /app
USER traceopsuser

EXPOSE 8080

HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/_stcore/health || exit 1

# Launch start.sh which coordinates FastAPI on 8000 and Streamlit on $PORT
CMD ["/bin/bash", "/app/start.sh"]
