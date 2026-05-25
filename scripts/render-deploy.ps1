$ErrorActionPreference = "Stop"
$OwnerId = "tea-d8a1ategvqtc73cebueg"
$Key = ((Get-Content "$env:USERPROFILE\.render\cli.yaml" | Where-Object { $_ -match '^\s+key:' }) -replace '^\s+key:\s*', '').Trim()
$Headers = @{
    Authorization = "Bearer $Key"
    Accept        = "application/json"
    "Content-Type" = "application/json"
}

function Invoke-Render($Method, $Uri, $Body) {
    if ($Body) {
        return Invoke-RestMethod -Uri $Uri -Headers $Headers -Method $Method -Body ($Body | ConvertTo-Json -Depth 12)
    }
    return Invoke-RestMethod -Uri $Uri -Headers $Headers -Method $Method
}

Write-Host "Creating PostgreSQL database..."
$dbBody = @{
    name         = "breathe-esg-db"
    ownerId      = $OwnerId
    plan         = "free"
    version      = "16"
    databaseName = "breathe_esg"
    databaseUser = "breathe_esg"
}
$db = Invoke-Render POST "https://api.render.com/v1/postgres" $dbBody
$dbId = $db.id
Write-Host "Database id: $dbId"

Write-Host "Waiting for database to become available..."
$connectionString = $null
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 10
    $detail = Invoke-Render GET "https://api.render.com/v1/postgres/$dbId" $null
    $status = $detail.status
    Write-Host "  status: $status"
    if ($status -eq "available") {
        $conn = Invoke-Render GET "https://api.render.com/v1/postgres/$dbId/connection-info" $null
        if ($conn.internalConnectionString) {
            $connectionString = $conn.internalConnectionString
            break
        }
        if ($conn.externalConnectionString) {
            $connectionString = $conn.externalConnectionString
            break
        }
    }
}
if (-not $connectionString) {
    throw "Database did not become available in time."
}

$repo = $env:RENDER_REPO
if (-not $repo) {
    $repo = "https://github.com/JaswanthPolarowthu07/breathe-esg-intake"
}

Write-Host "Creating web service from repo: $repo"
$serviceBody = @{
    type     = "web_service"
    name     = "breathe-esg-intake"
    ownerId  = $OwnerId
    repo     = $repo
    branch   = "master"
    autoDeploy = "yes"
    envVars  = @(
        @{ key = "DEBUG"; value = "False" }
        @{ key = "ALLOWED_HOSTS"; value = ".onrender.com" }
        @{ key = "SECRET_KEY"; generateValue = $true }
        @{ key = "DATABASE_URL"; value = $connectionString }
    )
    serviceDetails = @{
        runtime = "python"
        plan    = "starter"
        healthCheckPath = "/api/health/"
        envSpecificDetails = @{
            buildCommand = "bash build.sh"
            startCommand = "python manage.py migrate && python manage.py seed_demo --if-empty && gunicorn breathe_esg.wsgi:application --bind 0.0.0.0:`$PORT"
        }
    }
}
$service = Invoke-Render POST "https://api.render.com/v1/services" $serviceBody
Write-Host "Service created: $($service.service.id)"
Write-Host "Dashboard: $($service.service.dashboardUrl)"
if ($service.service.serviceDetails.url) {
    Write-Host "LIVE_URL=$($service.service.serviceDetails.url)"
}
