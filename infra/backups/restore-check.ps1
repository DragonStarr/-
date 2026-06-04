param(
  [Parameter(Mandatory = $true)]
  [string]$DumpPath
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $DumpPath)) {
  throw "Dump not found: $DumpPath"
}

Write-Output "restore-check-input=$DumpPath"
Write-Output "Run this on an isolated test database, never on production."
