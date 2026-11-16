# Arranque local del MVP en el navegador (sin Docker Compose).
# Requisitos: PostgreSQL 16 + PostGIS con la base ya migrada y registrada (DATABASE_URL, o el contenedor
# de desarrollo `milpa-test-db` si hay Docker), el entorno Python (.venv) y el frontend compilado (apps/web/dist).
# Valores SOLO de desarrollo local (los mismos de las pruebas); no usar en un servidor real.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

# La API NO requiere Docker. Solo necesita un PostgreSQL 16 + PostGIS accesible por DATABASE_URL.
# Si ya definio DATABASE_URL (PostgreSQL local o remoto), se usa tal cual. Si no, y Docker existe,
# se intenta el contenedor de desarrollo `milpa-test-db`; si tampoco, se explica que falta.
if (-not $env:DATABASE_URL) {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker) {
    docker start milpa-test-db 2>$null | Out-Null
    for ($i = 0; $i -lt 30; $i++) {
      docker exec milpa-test-db pg_isready -U postgres 2>$null | Out-Null
      if ($LASTEXITCODE -eq 0) { break }
      Start-Sleep -Seconds 1
    }
    $env:DATABASE_URL = "postgresql+psycopg://milpa_app:app_test_only@127.0.0.1:55432/milpa_dev"
  } else {
    Write-Error "Falta DATABASE_URL y no hay Docker. Defina DATABASE_URL apuntando a un PostgreSQL 16 + PostGIS ya migrado (ver docs/DEPLOYMENT.md). El PDF no necesita Docker ni Pango."
    exit 2
  }
}
$env:JWT_SECRET = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
$env:DATA_DIR = "./data"
$env:MILPA_MODE = "sandbox"
$env:MUNICIPAL_BOUNDARY_FILE = "./regions/jocotan_chiquimula_boundary.geojson"   # rechaza parcelas fuera de Jocotan
$env:DEMO_PUBLIC_ACCESS = "true"      # LAUNCH DEMO entra sin login (alcance limitado)
$env:RATE_LIMIT_PER_MIN = "1200"       # la interfaz hace decenas de consultas por pantalla; el valor por defecto (120) es para servidores
$env:PYTHONUTF8 = "1"

Write-Host "MILPA RESILIENTE -> http://127.0.0.1:8000  (Ctrl+C para detener)"
Start-Process "http://127.0.0.1:8000"
& .\.venv\Scripts\python.exe -m uvicorn --factory api.main:create_app --host 127.0.0.1 --port 8000
