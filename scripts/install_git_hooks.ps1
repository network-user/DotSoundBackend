$ErrorActionPreference = "Stop"
$root = git rev-parse --show-toplevel
Set-Location $root
git config core.hooksPath .githooks
Write-Host "core.hooksPath set to .githooks (pre-push runs boundary policy check)."
