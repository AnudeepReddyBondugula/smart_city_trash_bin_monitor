Write-Host "Ensuring infrastructure is running..."

# Go to repo root and start only infrastructure services
$repoRoot = Resolve-Path "$PSScriptRoot\..\..\.."
Set-Location $repoRoot
docker compose -f docker-compose.yml up -d postgres kafka
Set-Location "$repoRoot\services\data-simulator"

Write-Host "Waiting for PostgreSQL to be ready..."
while ($true) {
    # Check if postgres is ready
    $result = docker exec smartbin_postgres pg_isready -U $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "postgres" })
    if ($result -match "accepting connections") {
        break
    }
    Start-Sleep -Seconds 2
}

Write-Host "Infrastructure is ready."
Write-Host "Starting simulator..."

$env:PYTHONPATH = "."
python src/main.py
