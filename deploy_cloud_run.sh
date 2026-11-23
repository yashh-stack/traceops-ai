#!/usr/bin/env bash
# Deploy TraceOps AI Circuit-Breaker Engine to Google Cloud Run
# Serves FastAPI proxy directly on public Cloud Run endpoint
# Google DeepMind x Cloud Startup Buildathon India 2026

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-builder-cup-511710}"
REGION="${GCP_REGION:-asia-south1}"
SERVICE_NAME="traceops-ai-engine"
IMAGE_TAG="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "=========================================================="
echo "⚡ Deploying TraceOps AI Engine to Google Cloud Run"
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION} (Mumbai)"
echo "Service:  ${SERVICE_NAME}"
echo "Server:   FastAPI (Microsecond Synchronous Hot-Path Proxy)"
echo "=========================================================="

# 1. Build & Push via Google Cloud Build
echo "[1/3] Building container image via Google Cloud Build..."
gcloud builds submit --tag "${IMAGE_TAG}" .

# 2. Deploy Cloud Run Service
echo "[2/3] Deploying engine to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_TAG}" \
    --project "${PROJECT_ID}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 2 \
    --concurrency 80 \
    --timeout 30 \
    --set-env-vars="TRACEOPS_MODE=enforce,MAX_IDENTICAL_CALLS=3,MAX_COST_USD=0.50,DRIFT_THRESHOLD=0.55,GEMINI_JUDGE_MODEL=gemini-3.5-flash-lite,GEMINI_BASELINE_MODEL=gemini-3.8-flash"

# 3. Retrieve live service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format 'value(status.url)')

echo "=========================================================="
echo "✅ Deployment Complete!"
echo "Service URL: ${SERVICE_URL}"
echo "Health Check: curl ${SERVICE_URL}/health"
echo "Evaluate API: curl -X POST ${SERVICE_URL}/v1/evaluate-step -H 'Content-Type: application/json' -d '{\"tool_name\":\"query_gke_telemetry\",\"arguments\":{}}'"
echo "=========================================================="
