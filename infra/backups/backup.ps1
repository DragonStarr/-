$ErrorActionPreference = "Stop"

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $PSScriptRoot "operator_day-$stamp.dump"

docker compose -f ..\compose\prod.yml exec -T postgres `
  pg_dump -U operator -d operator_day -Fc | Set-Content -LiteralPath $target -Encoding Byte

Write-Output "backup=$target"
