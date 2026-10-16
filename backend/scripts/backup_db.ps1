<#
.SYNOPSIS
    Creates a compressed PostgreSQL backup (custom format) for IntelliINPI.

.DESCRIPTION
    Reads DATABASE_URL from the environment (driver suffix "+psycopg" is
    stripped) and runs pg_dump -Fc. No credentials are hardcoded or echoed.

.PARAMETER OutDir
    Directory where the .dump file is written. Created if missing.

.EXAMPLE
    $env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/intelliinpi_app"
    .\backup_db.ps1 -OutDir "D:\backups\intelliinpi"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$OutDir
)

$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) {
    Write-Error "DATABASE_URL nao definido no ambiente."
    exit 2
}

if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
    Write-Error "pg_dump nao encontrado no PATH."
    exit 3
}

# postgresql+psycopg://user:pass@host:port/db  ->  postgresql://user:pass@host:port/db
$dbUrl = $env:DATABASE_URL -replace '\+psycopg', ''

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$target = Join-Path $OutDir ("intelliinpi_{0}.dump" -f $stamp)

Write-Host "Criando backup em: $target"
& pg_dump --format=custom --no-owner --no-privileges --file="$target" "$dbUrl"

if ($LASTEXITCODE -ne 0 -or -not (Test-Path $target)) {
    Write-Error "Falha ao criar o backup (exit=$LASTEXITCODE)."
    exit 1
}

$size = (Get-Item $target).Length
Write-Host ("Backup concluido: {0} ({1:N0} bytes)" -f $target, $size)
exit 0
