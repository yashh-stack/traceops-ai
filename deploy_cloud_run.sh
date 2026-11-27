#!/usr/bin/env bash
# Deploy TraceOps AI (Streamlit HUD + Background FastAPI Proxy) to Google Cloud Run
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-builder-cup-511710}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="traceops-ai-engine"
ADMIN_TOKEN="${TRACEOPS_ADMIN_TOKEN:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"

echo "=========================================================="
echo "⚡ Deploying TraceOps AI to Google Cloud Run"
echo "Project: ${PROJECT_ID} | Region: ${REGION} | Service: ${SERVICE_NAME}"
echo "=========================================================="

gcloud config set project "${PROJECT_ID}"

echo "[1/3] Deploying revision via Cloud Build (canary --no-traffic if service exists)..."
TRAFFIC_FLAGS=""
if gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    TRAFFIC_FLAGS="--no-traffic --tag canary"
fi

gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    ${TRAFFIC_FLAGS} \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 2 \
    --concurrency 80 \
    --timeout 30 \
    --set-env-vars="TRACEOPS_ENV=production,TRACEOPS_MODE=enforce,MAX_IDENTICAL_CALLS=3,MAX_COST_USD=0.50,DRIFT_THRESHOLD=0.55,GEMINI_JUDGE_MODEL=gemini-3.5-flash-lite,GEMINI_BASELINE_MODEL=gemini-3.8-flash,TRACEOPS_ADMIN_TOKEN=${ADMIN_TOKEN}"

CANARY_URL="$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format "value(status.traffic[?tag=='canary'].url)")"
CANARY_URL="${CANARY_URL:-$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format "value(status.url)")}"

echo "[2/3] Smoke testing canary (${CANARY_URL}/_stcore/health)..."
curl -fsS "${CANARY_URL}/_stcore/health" >/dev/null

echo "[3/3] Shifting 100% traffic to verified revision..."
gcloud run services update-traffic "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --to-latest
SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format 'value(status.url)')"

echo "=========================================================="
echo "✅ Deployment Live & Verified: ${SERVICE_URL}"
echo "=========================================================="
