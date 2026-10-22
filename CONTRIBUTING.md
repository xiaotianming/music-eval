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

需要模型时改用 `uv sync --locked --extra dev --extra models`。SongEval 和 FAD 的独立环境安装方式见 [依赖说明](docs/dependencies.md)。

前后端开发需要两个终端：

```powershell
# 终端 1，项目根目录
./.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 18763
# 终端 2
cd frontend
npm run dev
```

修改后端后重启服务。同一数据目录运行一个后端进程。前端开发地址为 Vite 输出的本地 URL，API 代理到 18763 端口。

## 提交前检查

```powershell
./.venv/Scripts/python.exe -m pytest -q
cd frontend
npm run build
cd ..
git diff --check
```

基础测试使用合成音频。模型推理和性能检查按需运行 `scripts/model_smoke.py`、`scripts/fad_smoke.py`、`scripts/benchmark.py`。共享复现样例时使用合成或许可明确的音频。

## 评估逻辑变更

- 修复实际问题，并补充能观察到行为差异的测试；避免只复述实现。
- 修改重采样、分窗、归一化、翻译、模型修订或聚合方法时，检查缓存键和协议版本，更新 [protocol.md](docs/protocol.md)。旧结果不得被当作新协议的分数。
- 测试记录写明数据来源、执行方式和输出，性能测量另附硬件和参数。
- 锁文件应随依赖更新提交，不手工改写哈希。详见 [依赖维护](docs/dependencies.md)。

## Pull Request

描述解决的问题、最终行为、验证方式，以及对评估结果/缓存/兼容性的影响。界面变更附截图；涉及指标的变更附协议说明或小型可复现案例。一次 PR 尽量只解决一个问题。

贡献的原创代码按 MIT 许可证提供，第三方代码和素材保留对应许可。讨论请围绕具体技术问题，尊重其他参与者的隐私。
