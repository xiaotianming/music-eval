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

Python 固定 3.11；Node.js 采用根目录 `.node-version` 指定的 22 LTS。主环境是从源码运行的应用，未宣称支持 PyPI wheel 安装。uv 环境通常不包含 pip，请用 `uv sync` / `uv pip` 管理依赖。

FADtk 需要 NumPy 1.x，而主环境使用 NumPy 2.x；SongEval 的上游栈也独立冻结。CPU torch/torchaudio/torchvision 需要从官方 CPU 索引安装，不能将 CUDA 轮子加入默认安装。

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

SongEval 使用同样步骤，但替换为 `requirements-songeval`。三件套版本必须同时在 `.in` 和安装脚本中保持一致；从生成锁文件中排除三件套，是为了由 CPU 索引显式安装，而不是允许任意浮动版本。

前端更新需要同步清单与锁文件：

```powershell
cd frontend
npm install --save-dev --save-exact <package>@<version>
npm ci
npm run build
npm audit --audit-level=high
```

前端仓库 `.npmrc` 固定官方 npm registry；不修改开发者全局配置。不要提交私人镜像凭据。CI 的 `--locked` 和 `npm ci` 会在清单与锁文件不一致时失败。

## 模型更新与离线使用

仅更新库版本不能替代模型修订记录。更新模型时需要同步 `models.lock.json`、协议/缓存版本及真实 CPU smoke 记录。SongEval 会检查源码修订、关键源码是否修改及权重哈希。

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

审计只按公开版本通告匹配，不能证明应用没有漏洞。可选模型栈与上游兼容约束较多，应单独评估升级影响并运行真实模型验证；不要为了消除报告条目而不经验证地合并或跨大版本升级环境。
