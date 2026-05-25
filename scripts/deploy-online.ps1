# Deploy Breathe ESG intake app online (Render via GitHub, or Railway direct)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$git = "C:\Program Files\Git\bin\git.exe"
$gh = "C:\Program Files\GitHub CLI\gh.exe"

Write-Host "=== Breathe ESG — deploy online ===" -ForegroundColor Cyan

& $gh auth status 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Opening GitHub login in your browser..." -ForegroundColor Yellow
    & $gh auth login -h github.com -p https -w -s repo
}

if (-not (& $git rev-parse HEAD 2>$null)) {
    & $git add -A
    & $git commit -m "Breathe ESG intake review prototype — ready for deployment"
}

$repoName = "breathe-esg-intake"
Write-Host "Creating GitHub repo '$repoName' (if needed) and pushing..." -ForegroundColor Yellow
& $gh repo create $repoName --public --source=. --remote=origin --push 2>$null
if ($LASTEXITCODE -ne 0) {
    & $git remote add origin "https://github.com/$(gh api user -q .login)/$repoName.git" 2>$null
    & $git push -u origin master 2>$null
    if ($LASTEXITCODE -ne 0) { & $git push -u origin main }
}

$login = & $gh api user -q .login
$repoUrl = "https://github.com/$login/$repoName"
$renderDeploy = "https://render.com/deploy?repo=$repoUrl"

Write-Host ""
Write-Host "Repo: $repoUrl" -ForegroundColor Green
Write-Host "Opening Render Deploy (connect repo, use render.yaml Blueprint)..." -ForegroundColor Green
Start-Process $renderDeploy
Write-Host ""
Write-Host "On Render: approve the Blueprint, wait ~5 min, then open your *.onrender.com URL." -ForegroundColor Cyan
