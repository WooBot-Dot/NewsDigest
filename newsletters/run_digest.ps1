# run_digest.ps1 - fetches daily Norway news from NRK, VG, Dagbladet, E24, Aftenposten
# This script is a placeholder. Run on Windows host or adapt for Linux cron.

$today = Get-Date -Format yyyy-MM-dd
$archiveDir = Join-Path $PSScriptRoot "news"
if (!(Test-Path $archiveDir)) { New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null }
$outHtml = Join-Path $archiveDir "$today.html"
$outMd = Join-Path $archiveDir "$today.md"

# Placeholder: call the real fetcher (to be implemented). For now, copy template.
$template = Join-Path $PSScriptRoot "template.html"
if (Test-Path $template) { Copy-Item $template $outHtml -Force }

"# Digest for $today`n`n(This is a placeholder - implement fetch logic)" | Out-File -FilePath $outMd -Encoding utf8

Write-Output "Saved placeholders: $outHtml and $outMd"
