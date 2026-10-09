<#
.SYNOPSIS
    IntelliINPI - one-shot local bootstrap.

.DESCRIPTION
    Prepares everything needed to run IntelliINPI locally on Windows:
      1. Creates the dedicated PostgreSQL database (intelliinpi_app) if missing.
      2. Creates the backend virtualenv and installs Python dependencies.
      3. Creates .env from .env.example (if missing).
      4. Runs the Alembic migrations (schema).
      5. Runs the idempotent seed (Master Admin, modules, roles, permissions).
      6. Applies the database search indexes (pg_trgm / unaccent / FTS).
      7. Validates the backend with a healthcheck.
      8. Prints the next steps (frontend + INPI ingestion).

.PARAMETER DatabaseUrl
    SQLAlchemy URL. Defaults to the dedicated local database.

.PARAMETER SkipDb
    Skip creating the database (assume it already exists).

.PARAMETER SkipIndexes
    Skip applying the database/ SQL index scripts.

.PARAMETER PsqlPath
    Path to psql.exe. Defaults to the PostgreSQL 16 install location.

.EXAMPLE
    ./scripts/bootstrap.ps1
#>
[CmdletBinding()]
param(
    [string]$DatabaseUrl = "postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_app",
    [switch]$SkipDb,
    [switch]$SkipIndexes,
    [string]$PsqlPath = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host "  [!] $msg" -ForegroundColor Yellow }

# --- Resolve paths ----------------------------------------------------------
$Root       = Split-Path -Parent $PSScriptRoot
$Backend    = Join-Path $Root "backend"
$Venv       = Join-Path $Backend ".venv"
$Py         = Join-Path $Venv "Scripts\python.exe"
$EnvFile    = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
$DatabaseDir = Join-Path $Root "database"

Write-Host "IntelliINPI bootstrap" -ForegroundColor Magenta
Write-Host "Root: $Root"

# --- Parse the DB name/host from the URL for createdb -----------------------
if ($DatabaseUrl -match "://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)") {
    $DbUser = $Matches[1]; $DbPass = $Matches[2]
    $DbHost = $Matches[3]; $DbPort = $Matches[4]; $DbName = $Matches[5]
} else {
    throw "Could not parse DatabaseUrl: $DatabaseUrl"
}

# --- 1. Database ------------------------------------------------------------
if (-not $SkipDb) {
    Write-Step "1/7 Creating database '$DbName' (if missing)"
    if (-not (Test-Path $PsqlPath)) {
        Write-Warn2 "psql not found at $PsqlPath; set PGPASSWORD and create the DB manually."
    } else {
        $env:PGPASSWORD = $DbPass
        $exists = & $PsqlPath -U $DbUser -h $DbHost -p $DbPort -tAc `
            "SELECT 1 FROM pg_database WHERE datname='$DbName'"
        if ($exists -ne "1") {
            & $PsqlPath -U $DbUser -h $DbHost -p $DbPort -c "CREATE DATABASE `"$DbName`""
            Write-Ok "Database '$DbName' created."
        } else {
            Write-Ok "Database '$DbName' already exists."
        }
    }
} else {
    Write-Step "1/7 Database creation skipped (-SkipDb)"
}

# --- 2. Virtualenv + dependencies -------------------------------------------
Write-Step "2/7 Python virtualenv and dependencies"
# --- 3. .env ----------------------------------------------------------------
Write-Step "3/7 Environment file"
if (-not (Test-Path $EnvFile)) {
    Copy-Item $EnvExample $EnvFile
    # Point the .env at the database we just prepared.
    (Get-Content $EnvFile) -replace '^DATABASE_URL=.*', "DATABASE_URL=$DatabaseUrl" |
        Set-Content $EnvFile
    Write-Ok ".env created from .env.example."
} else {
    Write-Ok ".env already exists (left untouched)."
}

$env:DATABASE_URL = $DatabaseUrl

# --- 4. Migrations ----------------------------------------------------------
Write-Step "4/7 Alembic migrations"
Push-Location $Backend
try {
    & $Py -m alembic upgrade head
    Write-Ok "Schema up to date."
} finally { Pop-Location }

# --- 5. Seed ----------------------------------------------------------------
Write-Step "5/7 Seed (master admin, modules, roles, permissions)"
Push-Location $Backend
try {
    & $Py -m app.seed
    Write-Ok "Seed complete."
} finally { Pop-Location }

# --- 6. Search indexes ------------------------------------------------------
if (-not $SkipIndexes) {
    Write-Step "6/7 Database search indexes"
    if (-not (Test-Path $PsqlPath)) {
        Write-Warn2 "psql not found; skipping index scripts."
    } else {
        $env:PGPASSWORD = $DbPass
        foreach ($sql in @("01_extensions.sql", "02_indexes.sql", "03_fts_search.sql")) {
            $path = Join-Path $DatabaseDir $sql
            if (Test-Path $path) {
                & $PsqlPath -U $DbUser -h $DbHost -p $DbPort -d $DbName `
                    -v ON_ERROR_STOP=1 -f $path | Out-Null
                Write-Ok "Applied $sql"
            }
        }
    }
} else {
    Write-Step "6/7 Index scripts skipped (-SkipIndexes)"
}

# --- 7. Healthcheck ---------------------------------------------------------
Write-Step "7/7 Healthcheck"
Push-Location $Backend
try {
    & $Py -c "from app.main import app; print('FastAPI app import OK:', app.title)"
    Write-Ok "Backend imports cleanly."
} finally { Pop-Location }

Write-Host "`nBootstrap finished." -ForegroundColor Magenta
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  Backend : cd backend; .\.venv\Scripts\activate; uvicorn app.main:app --reload --port 8000"
Write-Host "  Frontend: cd frontend; npm install; npm run dev"
Write-Host "  Ingestao: python -m ingestion.import_all --category marcas --category patentes"

if (-not (Test-Path $Py)) {
    python -m venv $Venv
    Write-Ok "Virtualenv created at $Venv"
} else {
    Write-Ok "Virtualenv already exists."
}
& $Py -m pip install --upgrade pip | Out-Null
& $Py -m pip install -r (Join-Path $Backend "requirements.txt")
& $Py -m pip install -r (Join-Path $Root "ingestion\requirements.txt")
Write-Ok "Dependencies installed."
