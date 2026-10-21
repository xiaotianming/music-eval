# 依赖与复现

## 环境分层

| 环境 | 安装来源 | 作用 |
|---|---|---|
| 主环境 `.venv` | `pyproject.toml` + `uv.lock` | FastAPI、音频检查、统计、服务 |
| `models` extra | 同一份 `uv.lock` | CPU PyTorch、Transformers、CLAP 与本地翻译 |
| `dev` extra | 同一份 `uv.lock` | pytest / HTTP 测试客户端 |
| `.venv-songeval` | `requirements-songeval.lock` + 安装脚本固定 CPU torch 三件套 | MuQ / SongEval |
| `.venv-fad` | `requirements-fad.lock` + 安装脚本固定 CPU torch 三件套 | FADtk / LAION CLAP |
| 前端 | `frontend/package-lock.json` | React、TypeScript、Vite |
| 模型资产 | `models.lock.json` | Hugging Face / Git 的固定修订与 SongEval 权重哈希 |

项目从源码运行，使用 Python 3.11 和 `.node-version` 指定的 Node.js 22 LTS。通过 `uv sync` / `uv pip` 管理 Python 依赖。

FADtk 需要 NumPy 1.x，主环境使用 NumPy 2.x，因此分开安装；SongEval 的上游依赖也单独锁定。torch、torchaudio 和 torchvision 从官方 CPU 索引安装。

## 安装选择

```powershell
# 只用无需模型的功能
./scripts/setup.ps1
# 加上 CLAP 与中文翻译
./scripts/setup.ps1 -Models
# 以下均为可选，独立安装且不重建已存在的环境
./scripts/setup-songeval.ps1
./scripts/setup-fad.ps1
```

`setup.ps1` 安装 `dev` extra 以方便源码开发；重新以不带 `-Models` 的方式同步主环境可能移除模型 extra。需要模型时始终带该参数。

FFmpeg 由 `imageio-ffmpeg` 提供，不要求系统 PATH 中已有 FFmpeg。音频读取优先使用 libsndfile，无法解码时才尝试 FFmpeg。可选模型依赖、源码和权重都不会随 Git 仓库发布。

## 更新依赖

主环境修改精确版本后运行：

```powershell
uv lock
uv sync --locked --extra dev --extra models
uv pip check --python .venv/Scripts/python.exe
```

独立环境先修改对应 `.in`，再生成锁文件；以下以 FAD 为例：

```powershell
uv pip compile requirements-fad.in --python 3.11 --no-emit-package torch --no-emit-package torchaudio --no-emit-package torchvision -o requirements-fad.lock
./scripts/setup-fad.ps1
uv pip check --python .venv-fad/Scripts/python.exe
```

SongEval 使用同样步骤，将文件名替换为 `requirements-songeval`。torch、torchaudio 和 torchvision 的版本同时写在 `.in` 和安装脚本中；锁文件生成时排除这三个包，由安装脚本从 CPU 索引安装指定版本。

前端更新需要同步清单与锁文件：

```powershell
cd frontend
npm install --save-dev --save-exact <package>@<version>
npm ci
npm run build
npm audit --audit-level=high
```

前端通过项目内的 `.npmrc` 使用官方 npm registry。CI 使用 `uv --locked` 和 `npm ci` 检查清单与锁文件是否一致。

## 模型更新与离线使用

更新模型时同步 `models.lock.json`、协议和缓存版本，并重新记录 CPU 推理结果。SongEval 会校验源码修订、关键源文件和权重哈希。

```powershell
./.venv/Scripts/python.exe scripts/download_models.py clap translation muq fad_clap roberta
```

首次下载需要网络和足够磁盘空间。下载后先运行所需指标，再开启离线模式验证。RoBERTa 项只下载配置与分词器；FAD 的完整权重来自固定音乐 CLAP checkpoint。`.env.example` 仅说明环境变量，不会被自动执行。

## 依赖审计

```powershell
uvx pip-audit --path .venv/Lib/site-packages
uvx pip-audit --path .venv-songeval/Lib/site-packages
uvx pip-audit --path .venv-fad/Lib/site-packages
```

模型栈的已知通告及迁移安排见 [安全状态](security-status.md)。升级各环境后运行依赖检查和对应的模型推理测试。
