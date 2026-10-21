param([switch]$Models)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw '请先安装 uv: https://docs.astral.sh/uv/' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw '请先安装 Node.js 20.19+ LTS' }
$syncArgs = @('sync', '--locked', '--extra', 'dev')
if ($Models) { $syncArgs += @('--extra', 'models') }
& uv @syncArgs
if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败' }
Push-Location frontend
try {
  & npm ci --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败' }
  & npm run build
  if ($LASTEXITCODE -ne 0) { throw '前端构建失败' }
} finally { Pop-Location }
Write-Output '安装完成。运行 ./scripts/start.ps1 启动。'
