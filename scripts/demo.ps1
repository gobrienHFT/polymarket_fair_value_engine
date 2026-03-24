param(
    [string]$RunId = "sample-demo"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

Set-Location $repoRoot

python -m pip install -e ".[dev]"
pytest -q

$backtestJson = (pmfe backtest --sample --run-id $RunId | Out-String).Trim()
Write-Output $backtestJson

$reportJson = (pmfe report --run-id $RunId | Out-String).Trim()
Write-Output $reportJson

$outputDir = ($reportJson | ConvertFrom-Json).output_dir
Write-Host "Output directory: $outputDir"
