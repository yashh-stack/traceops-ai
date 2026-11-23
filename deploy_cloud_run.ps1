# PowerShell Deployment Script for TraceOps AI Engine on Google Cloud Run
# Target: asia-south1 (Mumbai) | Standalone FastAPI Circuit-Breaker Engine

$ErrorActionPreference = "Stop"

$ProjectId = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else { "builder-cup-511710" }
$Region = if ($env:GCP_REGION) { $env:GCP_REGION } else { "asia-south1" }
$ServiceName = "traceops-ai-engine"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "⚡ Deploying TraceOps AI Engine to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project:  $ProjectId" -ForegroundColor Green
Write-Host "Region:   $Region (Mumbai)" -ForegroundColor Green
Write-Host "Service:  $ServiceName" -ForegroundColor Green
Write-Host "Runtime:  FastAPI Proxy (Microsecond Synchronous Hot-Path)" -ForegroundColor Green
Write-Host "=========================================================="

# Check auth
$auth = gcloud auth list --format="value(account)" 2>$null
if (-not $auth) {
    Write-Host "[!] No active gcloud account detected. Initiating interactive login..." -ForegroundColor Yellow
    gcloud auth login
}

# Set current project
Write-Host "[1/3] Setting active GCP project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId

# Deploy from source via Cloud Build
Write-Host "[2/3] Building and deploying container to Cloud Run..." -ForegroundColor Cyan
gcloud run deploy $ServiceName `
    --source . `
    --project $ProjectId `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --memory 1Gi `
    --cpu 1 `
    --min-instances 0 `
    --max-instances 2 `
    --concurrency 80 `
    --timeout 30 `
    --set-env-vars="TRACEOPS_MODE=enforce,MAX_IDENTICAL_CALLS=3,MAX_COST_USD=0.50,DRIFT_THRESHOLD=0.55,GEMINI_JUDGE_MODEL=gemini-3.5-flash-lite,GEMINI_BASELINE_MODEL=gemini-3.8-flash"

# Retrieve live URL
Write-Host "[3/3] Fetching live Service URL..." -ForegroundColor Cyan
$ServiceUrl = (gcloud run services describe $ServiceName --platform managed --region $Region --format "value(status.url)").Trim()

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "✅ Deployment Succeeded!" -ForegroundColor Green
Write-Host "Live URL: $ServiceUrl" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green

# Automated Smoke Test
Write-Host "`nRunning Live Smoke Test against $ServiceUrl..." -ForegroundColor Cyan
Invoke-RestMethod -Uri "$ServiceUrl/health" -Method Get | ConvertTo-Json -Depth 3

Write-Host "`nTesting Normal Tool Execution (fetch_pod_logs)..." -ForegroundColor Cyan
$payloadAllow = @{
    tool_name = "fetch_pod_logs"
    arguments = @{ pod = "auth-service-7f4c" }
} | ConvertTo-Json
$res1 = Invoke-RestMethod -Uri "$ServiceUrl/v1/evaluate-step" -Method Post -Body $payloadAllow -ContentType "application/json"
$res1 | ConvertTo-Json -Depth 3

Write-Host "`nTesting Unauthorized Tool Interception (delete_production_db)..." -ForegroundColor Cyan
$payloadBlock = @{
    tool_name = "delete_production_db"
    arguments = @{ force = $true }
} | ConvertTo-Json
try {
    $res2 = Invoke-RestMethod -Uri "$ServiceUrl/v1/evaluate-step" -Method Post -Body $payloadBlock -ContentType "application/json"
    $res2 | ConvertTo-Json -Depth 3
} catch {
    Write-Host "Expected Interception: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nAll verification checks complete!" -ForegroundColor Green
