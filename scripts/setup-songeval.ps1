$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$lock = Get-Content models.lock.json -Raw | ConvertFrom-Json
New-Item -ItemType Directory -Force vendor | Out-Null
if (-not (Test-Path vendor/SongEval/.git)) {
  & git clone https://github.com/ASLP-lab/SongEval.git vendor/SongEval
  if ($LASTEXITCODE -ne 0) { throw 'SongEval 下载失败' }
}
& git -C vendor/SongEval checkout $lock.songeval.revision
if ($LASTEXITCODE -ne 0) { throw 'SongEval 修订切换失败' }
if (-not (Test-Path .venv-songeval/Scripts/python.exe)) {
  & uv venv .venv-songeval --python 3.11
  if ($LASTEXITCODE -ne 0) { throw '环境创建失败' }
}
& uv pip install --python .venv-songeval/Scripts/python.exe torch==2.7.0 torchaudio==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch 安装失败' }
& uv pip install --python .venv-songeval/Scripts/python.exe -r requirements-songeval.lock
if ($LASTEXITCODE -ne 0) { throw 'SongEval 依赖安装失败' }
if (-not (Test-Path vendor/SongEval/ckpt/model.safetensors)) { throw '上游未包含 ckpt/model.safetensors，请按官方说明获取并放入该路径' }
Write-Output 'SongEval 已就绪。MuQ 将在首次运行时下载到模型缓存。'
