# Scan all four DotSound repos for AI co-author trailers (read-only).
# To rewrite history, run strip_ai_coauthors.py per repo with --apply.

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
$Python = if ($env:DOTSOUND_PYTHON) { $env:DOTSOUND_PYTHON } else { "python" }

& $Python "$BackendRoot\scripts\strip_ai_coauthors.py" `
    --scan-all-dotsound `
    --report "$BackendRoot\.git-coauthor-backups\scan-report.json"

exit $LASTEXITCODE
