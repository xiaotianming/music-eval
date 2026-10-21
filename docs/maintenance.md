# 开源准备维护记录

日期：2026-10-21。此记录对应项目初始化和依赖维护，不覆盖或改写首次模型基准的原始环境。

## 本次整理

- 初始化本地 `main` 分支；准备首次提交，未创建远程仓库、推送或发布版本。
- 增加 MIT 许可证、第三方许可边界、贡献/安全/发布文档、更新记录、引用元数据，以及英文快速开始。
- 增加 GitHub Issue/PR 模板、固定修订的 Actions CI、依赖更新配置、编辑器/换行/忽略规则。
- 将 npm 锁文件中的镜像地址统一为官方源，固定 Node.js 22，并更新 Vite 修复版本。
- 更新核心 Python Web、上传、测试及模型 extra 的小型依赖补丁，保留模型权重和协议。
- 可选环境安装脚本复用已存在的虚拟环境，避免重复执行时重建环境。

## 验证

- 已更新主环境：17 项 Python 测试通过。
- 全新、未安装 `models` extra 的 `.cache/ci-core` 环境：17 项测试通过。
- `npm ci`、TypeScript 检查、Vite 6.4.5 生产构建通过。
- JSON/YAML/CITATION 文件可解析，Markdown 本地文件链接有效，PowerShell 安装脚本通过语法解析。
- `uv pip check` 检查主环境及两个独立环境，未发现依赖冲突。
- 核心 + 测试依赖的精确版本导出审计无已知漏洞；前端 npm audit 无已知漏洞。研究模型栈不属于该零漏洞结论，详见 [安全状态](security-status.md)。
- 模型 extra 更新后，固定资产的中文翻译及 CLAP 离线推理成功，保存于 [dependency-update-smoke.json](dependency-update-smoke.json)。未重做所有整曲性能基准；首次验收记录仍保留原测试环境与时间。

新 Starlette 对当前 HTTPX TestClient 后端有弃用提示，测试仍通过；没有将警告过滤或描述为无警告运行。远程 GitHub Actions 尚未实际执行；配置通过本地检查不等同于远程 CI 绿灯。

## 发布前仍需维护者处理

- 选择真实托管仓库并补齐仓库链接、维护者信息、安全私密报告入口。
- 核实项目 MIT 授权安排及第三方资产许可，特别是 SongEval 上游许可冲突。
- 对旧 Transformers 的已知通告安排兼容迁移，而不是宣称完整模型栈安全就绪。
