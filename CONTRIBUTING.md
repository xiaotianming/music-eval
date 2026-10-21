# 参与贡献

欢迎通过 Issue 和 Pull Request 改进 Music Eval。中文、英文均可。

## 开发环境

目前完整模型栈在 Windows 11 + Python 3.11 上验证。Node.js 使用 22 LTS；依赖通过 uv 和 npm 锁文件安装。

```powershell
uv sync --locked --extra dev
cd frontend
npm ci
npm run build
cd ..
./scripts/start.ps1
```

需要模型时改用 `uv sync --locked --extra dev --extra models`。SongEval 和 FAD 安装在独立环境，参见 [依赖说明](docs/dependencies.md)。不要把它们合并进主环境。

前后端开发需要两个终端：

```powershell
# 终端 1，项目根目录
./.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
# 终端 2
cd frontend
npm run dev
```

修改后端需要重启服务；默认只允许一个执行器占用同一数据目录。不要同时启动两个后端或额外的 uvicorn worker。前端开发地址为 Vite 输出的本地 URL，API 代理到 8000 端口。

## 提交前检查

```powershell
./.venv/Scripts/python.exe -m pytest -q
cd frontend
npm run build
cd ..
git diff --check
```

基础测试不下载模型。真实模型验证是手动、可选步骤：`scripts/model_smoke.py`、`scripts/fad_smoke.py`、`scripts/benchmark.py`。测试数据只用合成音频或有明确来源的上游示例；不要提交用户音乐、付费模型结果或未获授权的参考音乐。

## 评估逻辑变更

- 修复实际问题，并补充能观察到行为差异的测试；避免只复述实现。
- 修改重采样、分窗、归一化、翻译、模型修订或聚合方法时，检查缓存键和协议版本，更新 [protocol.md](docs/protocol.md)。旧结果不得被当作新协议的分数。
- 模拟结果、真实模型结果、性能测试和主观听感评价必须明确区分。不要填写未经运行的数字。
- 锁文件应随依赖更新提交，不手工改写哈希。详见 [依赖维护](docs/dependencies.md)。

## Pull Request

描述解决的问题、最终行为、验证方式，以及对评估结果/缓存/兼容性的影响。界面变更附截图；涉及指标的变更附协议说明或小型可复现案例。一次 PR 尽量只解决一个问题。

贡献原始代码按项目 MIT 许可证提供；你需要有权贡献提交的代码和素材。不要复制第三方模型代码、权重或媒体进仓库。保持讨论尊重、具体、围绕技术问题，避免人身攻击和披露他人隐私。
