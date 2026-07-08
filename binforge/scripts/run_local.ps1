Write-Host "Ensuring infrastructure is running..."

# Go to project root and run docker-compose
Set-Location ..
docker-compose -f docker-compose.infra.yml up -d
Set-Location binforge

Write-Host "Waiting for PostgreSQL to be ready..."
while ($true) {
    # Check if postgres is ready
    $result = docker exec smartbin_postgres pg_isready -U postgres
    if ($result -match "accepting connections") {
        break
    }
    Start-Sleep -Seconds 2
}

Write-Host "Infrastructure is ready."
Write-Host "Starting simulator..."

$env:PYTHONPATH = "."
python src/main.py
