# One-Shot Bootstrap: Connect Google Cloud (Workload Identity Federation) + GitHub Actions CD
# Automates end-to-end zero-key CI/CD + initial Cloud Run deployment for TraceOps AI.

$ErrorActionPreference = "Stop"

$ProjectId = if ($env:GCP_PROJECT_ID) { $env:GCP_PROJECT_ID } else { "builder-cup-511710" }
$Region = if ($env:GCP_REGION) { $env:GCP_REGION } else { "asia-south1" }
$ServiceName = "traceops-ai-engine"
$RepoOwner = "yashh-stack"
$RepoName = "traceops-ai"
$RepoFull = "$RepoOwner/$RepoName"
$PoolId = "github-actions-pool"
$ProviderId = "github-oidc"
$SaName = "traceops-deployer"
$SaEmail = "$SaName@$ProjectId.iam.gserviceaccount.com"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "TraceOps AI — End-to-End GCP + GitHub Actions CD Setup" -ForegroundColor Cyan
Write-Host "Project: $ProjectId | Region: $Region | Repo: $RepoFull" -ForegroundColor Green
Write-Host "=========================================================="

# 1. Authenticate gcloud interactively if needed
$acct = (gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>$null | Out-String).Trim()
if (-not $acct) {
    Write-Host "[1/6] Launching browser login for Google Cloud..." -ForegroundColor Yellow
    gcloud auth login
}
gcloud config set project $ProjectId

# 2. Authenticate GitHub CLI (reuse existing git credential helper token if available)
$ghToken = $env:GH_TOKEN
if (-not $ghToken) {
    try {
        $credOut = "protocol=https`nhost=github.com" | git credential fill
        $pwLine = ($credOut | Select-String "password=").Line
        if ($pwLine) { $ghToken = $pwLine.Replace("password=", "").Trim() }
    } catch {}
}
if ($ghToken) {
    $env:GH_TOKEN = $ghToken
} else {
    gh auth status 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[1b/6] Launching GitHub CLI login..." -ForegroundColor Yellow
        gh auth login
    }
}

# 3. Enable required GCP APIs
Write-Host "[2/6] Enabling Cloud Run, Cloud Build, Artifact Registry, IAM & Secret Manager APIs..." -ForegroundColor Cyan
gcloud services enable `
    run.googleapis.com `
    cloudbuild.googleapis.com `
    artifactregistry.googleapis.com `
    iamcredentials.googleapis.com `
    secretmanager.googleapis.com `
    --project $ProjectId

# 4. Provision least-privilege deployer Service Account + IAM roles
Write-Host "[3/6] Provisioning Service Account & Workload Identity Federation..." -ForegroundColor Cyan
$ProjectNumber = (gcloud projects describe $ProjectId --format="value(projectNumber)").Trim()

gcloud iam service-accounts describe $SaEmail --project $ProjectId 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    gcloud iam service-accounts create $SaName --display-name="TraceOps GitHub Deployer" --project $ProjectId
}

foreach ($role in @("roles/run.admin", "roles/artifactregistry.writer", "roles/cloudbuild.builds.builder", "roles/iam.serviceAccountUser", "roles/secretmanager.secretAccessor")) {
    gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$SaEmail" `
        --role="$role" `
        --condition=None `
        --quiet | Out-Null
}

# Workload Identity Pool & OIDC Provider restricted strictly to yashh-stack/traceops-ai
gcloud iam workload-identity-pools describe $PoolId --location="global" --project $ProjectId 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    gcloud iam workload-identity-pools create $PoolId `
        --project=$ProjectId `
        --location="global" `
        --display-name="GitHub Actions Pool"
}

gcloud iam workload-identity-pools providers describe $ProviderId --workload-identity-pool=$PoolId --location="global" --project $ProjectId 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    gcloud iam workload-identity-pools providers create-oidc $ProviderId `
        --project=$ProjectId `
        --location="global" `
        --workload-identity-pool=$PoolId `
        --display-name="GitHub OIDC" `
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" `
        --attribute-condition="assertion.repository == '$RepoFull'" `
        --issuer-uri="https://token.actions.githubusercontent.com"
}

$WifProvider = "projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolId/providers/$ProviderId"
gcloud iam service-accounts add-iam-policy-binding $SaEmail `
    --project=$ProjectId `
    --role="roles/iam.workloadIdentityUser" `
    --member="principalSet://iam.googleapis.com/projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolId/attribute.repository/$RepoFull" `
    --quiet | Out-Null

# 5. Generate secure admin token & push GitHub Actions Secrets
Write-Host "[4/6] Configuring GitHub Actions Secrets (zero long-lived GCP JSON keys)..." -ForegroundColor Cyan
$AdminToken = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 })) -replace '[+/=]', ''
gh secret set GCP_PROJECT_ID --repo $RepoFull --body $ProjectId
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --repo $RepoFull --body $WifProvider
gh secret set GCP_SERVICE_ACCOUNT --repo $RepoFull --body $SaEmail
gh secret set TRACEOPS_ADMIN_TOKEN --repo $RepoFull --body $AdminToken

if (Test-Path ".env") {
    $gemLine = (Select-String -Path ".env" -Pattern "^GEMINI_API_KEY=(.+)$" | Select-Object -First 1)
    if ($gemLine -and $gemLine.Matches.Groups[1].Value -and $gemLine.Matches.Groups[1].Value -ne "your_gemini_api_key_here") {
        gh secret set GEMINI_API_KEY --repo $RepoFull --body $gemLine.Matches.Groups[1].Value.Trim()
    }
}

# 6. Trigger immediate Cloud Run deploy workflow & wait for live URL
Write-Host "[5/6] Triggering GitHub Actions Cloud Run deployment..." -ForegroundColor Cyan
gh workflow run deploy-cloud-run.yml --repo $RepoFull --ref main

Write-Host "[6/6] Setup complete! Monitor live rollout:" -ForegroundColor Green
Write-Host "  gh run watch --repo $RepoFull" -ForegroundColor Yellow
Write-Host "  Or run manual local deploy anytime: .\deploy_cloud_run.ps1" -ForegroundColor Yellow
