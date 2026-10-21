# 仓库提交范围

仓库地址：<https://github.com/xiaotianming/music-eval>。

## 提交到 Git

| 文件 | 用途 |
|---|---|
| `backend/`、`frontend/src/`、`tests/`、`scripts/` | 应用、测试和安装代码 |
| `README*`、`docs/*.md`、许可证和贡献指南 | 安装、协议、使用和维护文档 |
| `pyproject.toml`、`uv.lock`、`requirements-*.in/.lock` | Python 依赖声明和精确版本 |
| `frontend/package.json`、`package-lock.json`、`.npmrc` | 前端依赖和公开 npm 源配置 |
| `models.lock.json` | 模型仓库修订、公开下载来源和校验值 |
| `.github/`、编辑器及构建配置 | CI、Issue/PR 模板和开发设置 |
| `.env.example` | 无凭据的环境变量示例 |
| `docs/*smoke.json`、`docs/benchmark-*.json`、`docs/preview.png` | 合成音频及公开上游示例的实测结果、演示截图 |

实测记录只收录可公开的指标、输入哈希和硬件参数。分享其他音频的报告前，检查提示词、文件名、路径和素材授权。

## 留在本机

| 文件或目录 | 原因 |
|---|---|
| `data/` | 用户音频、提示词、投票、SQLite、模型缓存和导出结果 |
| `vendor/` | 安装脚本下载的上游源码、权重和示例音频 |
| `.venv*`、`frontend/node_modules/` | 从锁文件重新安装的环境和依赖 |
| `frontend/dist/`、`build/`、`dist/` | 从源码构建的产物 |
| `.cache/`、测试缓存、日志和覆盖率报告 | 本机审计、开发和临时结果 |
| `.env*`（示例除外）、私钥、令牌 | 私人配置和访问凭据 |
| 音频、checkpoint、嵌入及压缩包 | 原始素材、大文件和运行缓存 |

这些路径和常见后缀已加入 `.gitignore`。如果以后确实需要提交合成音频测试夹具，应单独审查来源和大小，再对具体文件设置例外。

## 上传前检查

```powershell
git status --short
git ls-files
git diff --cached --check
```

检查所有待推送提交，而不只检查当前文件。已经进入历史的敏感数据需要从历史移除，并轮换相关凭据；新增忽略规则只影响后续未跟踪文件。
