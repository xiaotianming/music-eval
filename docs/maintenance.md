# 依赖更新记录

日期：2026-10-21。初始提交：`a1c1383`。

## 变更

- 增加 MIT 许可证、第三方说明、贡献指南、安全策略、发布流程和英文快速开始。
- 增加 GitHub Issue/PR 模板、Actions CI、依赖更新配置及编辑器设置。
- npm 使用官方源，Node.js 固定为 22 LTS，Vite 更新至 6.4.5。
- 更新核心 Web、上传和测试依赖，以及模型 extra 的 protobuf、sentencepiece 补丁。
- SongEval、FAD 安装脚本复用已有虚拟环境。

## 验证结果

- 主环境与全新的 `.cache/ci-core` 核心环境各通过 17 项 Python 测试。
- `npm ci`、TypeScript 检查及 Vite 生产构建通过。
- JSON、YAML、CITATION 和 PowerShell 脚本语法检查通过，Markdown 本地链接有效。
- 主环境及两个独立环境通过 `uv pip check`。
- 核心及测试依赖、前端依赖的审计均报告零已知漏洞。模型栈的已知通告见 [安全状态](security-status.md)。
- 更新后的中文翻译、CLAP 离线推理通过，结果见 [dependency-update-smoke.json](dependency-update-smoke.json)。整曲基准见 [首次验收](validation.md)。

Starlette TestClient 提示 HTTPX 后端将弃用，后续需要迁移。GitHub Actions 配置待首次远程运行。

发布准备见 [releasing.md](releasing.md)。
