# 依赖安全状态

检查日期：2026-10-21。

## 已完成的更新

| 依赖 | 本次版本 |
|---|---|
| Vite | 6.4.5，原为 6.3.5 |
| FastAPI | 0.156.8 |
| Starlette | 1.9.0 |
| python-multipart | 0.0.32 |
| pytest | 9.1.1 |
| protobuf | 5.29.6 |
| sentencepiece | 0.2.1 |

更新后，前端 `npm audit` 和核心加测试依赖的 `pip-audit` 均报告零已知漏洞。核心审计使用从 `uv.lock` 导出的完整版本清单。

## 待处理：Transformers

主环境的 `models` extra、SongEval 和 FAD 环境仍使用 `transformers==4.51.3`。审计报告涉及 checkpoint 转换器、部分模型的反序列化和配置加载，以及自定义生成模块加载路径。模型栈应只加载受信任资产，当前服务保持本地使用。

升级需完成 CLAP、MuQ 和 LAION 的 API 适配，核对分数及缓存协议，再运行离线推理和资源基准，最后更新三套锁文件。独立环境的其余传递依赖也需一并审查。

## 复现审计

```powershell
# 前端
cd frontend
npm audit --registry=https://registry.npmjs.org
cd ..

# 核心及测试依赖
New-Item -ItemType Directory -Force .cache | Out-Null
uv export --locked --extra dev --no-hashes --output-file .cache/core-requirements.txt
uvx pip-audit -r .cache/core-requirements.txt --no-deps --disable-pip

# 已安装的模型依赖，按环境检查
uvx pip-audit --path .venv/Lib/site-packages
uvx pip-audit --path .venv-songeval/Lib/site-packages
uvx pip-audit --path .venv-fad/Lib/site-packages
```

`uv export` 已列出全部传递依赖，审计时使用 `--no-deps` 直接检查这份清单。CI 执行核心测试、前端构建和前端审计；模型环境按上述命令单独检查。
