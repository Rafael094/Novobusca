<#
.SYNOPSIS
    Restores an IntelliINPI PostgreSQL backup into an EXPLICIT target database.

.DESCRIPTION
    Safety-first: requires -Confirm and refuses to run against the database named
    in DATABASE_URL. It never touches production implicitly. The target database
    is passed explicitly (e.g. a fresh isolated instance) and is dropped/recreated
    before restore so the result is reproducible.

.PARAMETER DumpFile
    Path to a .dump produced by backup_db.ps1 (custom format).

.PARAMETER TargetDatabase
    Name of the destination database (must differ from the source database).

.PARAMETER HostName / Port / Username
    Connection details for the ISOLATED target instance.

.EXAMPLE
    .\restore_db.ps1 -DumpFile "D:\backups\intelliinpi\intelliinpi_20260101_030000.dump" `
        -TargetDatabase "intelliinpi_restore_test" -HostName "localhost" -Port 5432 `
        -Username "postgres" -Confirm:$false
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,

    [Parameter(Mandatory = $true)]
    [string]$TargetDatabase,

    [string]$HostName = "localhost",
    [int]$Port = 5432,
    [string]$Username = "postgres",

    [switch]$Confirm
)

$ErrorActionPreference = "Stop"

if (-not $Confirm) {
    Write-Error "Restauracao exige -Confirm. Nenhuma acao foi executada."
    exit 2
}

if (-not (Test-Path $DumpFile)) {
    Write-Error "Dump nao encontrado: $DumpFile"
    exit 3
}

if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
    Write-Error "pg_restore nao encontrado no PATH."
    exit 4
}

# Guard rail: never restore over the database pointed at by DATABASE_URL.
if ($env:DATABASE_URL) {
    $sourceDb = ($env:DATABASE_URL -replace '\+psycopg', '').TrimEnd('/') -replace '^.*/', ''
    if ($sourceDb -eq $TargetDatabase) {
        Write-Error "Recusado: TargetDatabase '$TargetDatabase' == banco de origem. Use um banco isolado."
        exit 5
    }
}

Write-Host "Restaurando $DumpFile em $HostName`:$Port/$TargetDatabase"
& pg_restore --clean --if-exists --no-owner --no-privileges `
    --host=$HostName --port=$Port --username=$Username `
    --dbname=$TargetDatabase $DumpFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "pg_restore reportou exit=$LASTEXITCODE (pode haver avisos)."
    exit 1
}

Write-Host "Restauracao concluida em $TargetDatabase."
exit 0
