# Kura, one command. Windows PowerShell.
#   .\start.ps1
#
# Does nothing clever: checks Docker is actually running, then hands over to
# compose. The point is that a first run fails with a sentence you can act on
# instead of a wall of Go stack trace.

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Kura" -ForegroundColor Magenta -NoNewline
Write-Host "  local anime vault"
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "  Docker is not installed." -ForegroundColor Red
    Write-Host "  Get Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Write-Host ""
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Docker is installed but not running." -ForegroundColor Red
    Write-Host "  Start Docker Desktop, wait for the whale to settle, then run this again."
    Write-Host ""
    exit 1
}

$webPort = if ($env:KURA_WEB_PORT) { $env:KURA_WEB_PORT } else { "3000" }

Write-Host "  Building and starting. First run downloads a 12k title catalog," -ForegroundColor DarkGray
Write-Host "  so it takes a few minutes. Later runs are seconds." -ForegroundColor DarkGray
Write-Host ""

docker compose up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Compose failed. The usual cause is a port already in use:" -ForegroundColor Red
    Write-Host "  copy .env.example to .env and change KURA_WEB_PORT or KURA_API_PORT."
    Write-Host ""
    exit 1
}

Write-Host ""
Write-Host "  Seeding the catalog. Watch progress with:" -ForegroundColor DarkGray
Write-Host "    docker compose logs -f api"
Write-Host ""
Write-Host "  Open      " -NoNewline; Write-Host "http://localhost:$webPort" -ForegroundColor Cyan
Write-Host "  Sign in   demo@anime.app  /  demo1234"
Write-Host ""
Write-Host "  Stop with:  docker compose down"
Write-Host ""
