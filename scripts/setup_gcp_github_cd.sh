#!/usr/bin/env bash
# One-Shot Bootstrap: Connect Google Cloud (Workload Identity Federation) + GitHub Actions CD
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-builder-cup-511710}"
REGION="${GCP_REGION:-asia-south1}"
REPO_FULL="yashh-stack/traceops-ai"
POOL_ID="github-actions-pool"
PROVIDER_ID="github-oidc"
SA_NAME="traceops-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=========================================================="
echo "TraceOps AI — End-to-End GCP + GitHub Actions CD Setup"
echo "Project: ${PROJECT_ID} | Region: ${REGION} | Repo: ${REPO_FULL}"
echo "=========================================================="

if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" | grep -q .; then
  gcloud auth login
fi
gcloud config set project "${PROJECT_ID}"

if ! gh auth status >/dev/null 2>&1; then
  gh auth login
fi

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iamcredentials.googleapis.com \
  secretmanager.googleapis.com \
  --project="${PROJECT_ID}"

gcloud artifacts repositories describe traceops-repo --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud artifacts repositories create traceops-repo --repository-format=docker --location="${REGION}" --project="${PROJECT_ID}" --description="TraceOps AI Cloud Run containers"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"

gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "${SA_NAME}" --display-name="TraceOps GitHub Deployer" --project="${PROJECT_ID}"

for role in roles/run.admin roles/artifactregistry.writer roles/cloudbuild.builds.builder roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${role}" \
    --condition=None --quiet >/dev/null
done

gcloud iam workload-identity-pools describe "${POOL_ID}" --location="global" --project="${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "${POOL_ID}" --project="${PROJECT_ID}" --location="global" --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" --workload-identity-pool="${POOL_ID}" --location="global" --project="${PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --project="${PROJECT_ID}" --location="global" --workload-identity-pool="${POOL_ID}" \
    --display-name="GitHub OIDC" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository == '${REPO_FULL}'" \
    --issuer-uri="https://token.actions.githubusercontent.com"

WIF_PROVIDER="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO_FULL}" \
  --quiet >/dev/null

ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
gh secret set GCP_PROJECT_ID --repo "${REPO_FULL}" --body "${PROJECT_ID}"
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo "${REPO_FULL}" --body "${WIF_PROVIDER}"
gh secret set GCP_SERVICE_ACCOUNT --repo "${REPO_FULL}" --body "${SA_EMAIL}"
gh secret set TRACEOPS_ADMIN_TOKEN --repo "${REPO_FULL}" --body "${ADMIN_TOKEN}"

gh workflow run deploy-cloud-run.yml --repo "${REPO_FULL}" --ref main
echo "✅ Automated CI/CD triggered! Watch with: gh run watch --repo ${REPO_FULL}"
