# PowerShell Deployment Script for TraceOps AI on Google Cloud Run
# Target: asia-south1 (Mumbai) | Single-Container Streamlit HUD + FastAPI Engine

$ErrorActionPreference = "Continue"

$ProjectId = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else { "builder-cup-511710" }
$Region = if ($env:GCP_REGION) { $env:GCP_REGION } else { "asia-south1" }
$ServiceName = "traceops-ai-engine"
$AdminToken = if ($env:TRACEOPS_ADMIN_TOKEN) { $env:TRACEOPS_ADMIN_TOKEN } else {
    [Convert]::ToBase64String((1..24 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 })) -replace '[+/=]', ''
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "⚡ Deploying TraceOps AI to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project:  $ProjectId | Region: $Region | Service: $ServiceName" -ForegroundColor Green
Write-Host "Runtime:  Streamlit HUD (8080) + Background FastAPI Proxy (8000)" -ForegroundColor Green
Write-Host "=========================================================="

$auth = (cmd /c "gcloud auth list --format=value(account) 2>nul" | Out-String).Trim()
if (-not $auth) {
    Write-Host "[!] No active gcloud account detected. Initiating interactive login..." -ForegroundColor Yellow
    gcloud auth login
    if ($LASTEXITCODE -ne 0) { throw "gcloud auth login failed." }
}

Write-Host "[1/3] Setting active GCP project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host "[2/3] Deploying canary revision (--no-traffic) via Cloud Build..." -ForegroundColor Cyan
gcloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --no-traffic `
    --tag canary `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 2 `
    --concurrency 80 `
    --timeout 30 `
    --set-env-vars="TRACEOPS_ENV=production,TRACEOPS_MODE=enforce,MAX_IDENTICAL_CALLS=3,MAX_COST_USD=0.50,DRIFT_THRESHOLD=0.55,GEMINI_JUDGE_MODEL=gemini-3.5-flash-lite,GEMINI_BASELINE_MODEL=gemini-3.8-flash,TRACEOPS_ADMIN_TOKEN=$AdminToken"

$CanaryUrl = (gcloud run services describe $ServiceName --platform managed --region $Region --format "value(status.traffic[?tag=='canary'].url)").Trim()
if (-not $CanaryUrl) {
    $CanaryUrl = (gcloud run services describe $ServiceName --platform managed --region $Region --format "value(status.url)").Trim()
}

Write-Host "[3/3] Smoke testing canary ($CanaryUrl/_stcore/health) & promoting traffic..." -ForegroundColor Cyan
$hc = Invoke-WebRequest -Uri "$CanaryUrl/_stcore/health" -UseBasicParsing -TimeoutSec 20
if ($hc.StatusCode -ne 200) {
    throw "Canary health check failed with status $($hc.StatusCode)"
}

gcloud run services update-traffic $ServiceName --region $Region --project $ProjectId --to-latest | Out-Null
$ServiceUrl = (gcloud run services describe $ServiceName --platform managed --region $Region --format "value(status.url)").Trim()

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "✅ Deployment Live & Verified!" -ForegroundColor Green
Write-Host "Live URL: $ServiceUrl" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green
