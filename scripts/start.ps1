param([ValidateRange(1,65535)][int]$Port = 18763)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv/Scripts/python.exe')) { throw '请先运行 ./scripts/setup.ps1' }
if (-not (Test-Path 'frontend/dist/index.html')) { throw '请先构建前端：./scripts/setup.ps1' }
$env:PYTHONIOENCODING = 'utf-8'
Write-Output "Music Eval: http://127.0.0.1:$Port"
& ./.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
