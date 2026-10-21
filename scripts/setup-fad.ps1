$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .venv-fad/Scripts/python.exe)) {
  & uv venv .venv-fad --python 3.11
  if ($LASTEXITCODE -ne 0) { throw '环境创建失败' }
}
& uv pip install --python .venv-fad/Scripts/python.exe torch==2.7.0 torchaudio==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch 安装失败' }
& uv pip install --python .venv-fad/Scripts/python.exe -r requirements-fad.lock
if ($LASTEXITCODE -ne 0) { throw 'FAD 依赖安装失败' }
Write-Output 'FAD 独立环境已安装。首次运行需联网下载音乐 CLAP 权重。'
