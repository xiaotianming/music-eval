# Changelog

遵循 [Semantic Versioning](https://semver.org/)。在发布标签之前，以下内容仍属未发布版本。

## [Unreleased] — 0.1.0

### Added

- 满分 100 的综合评分，包含分项贡献、缺项覆盖率及历史任务快照计算；模型汇总只纳入完整评分。

- 中文本地网页：批量导入、作品对比、任务管理、模型报告及可选匿名 A/B。
- CPU 基础音频检查、音乐 CLAP、本地中文翻译、SongEval 和可选参考集 FAD。
- 持久任务、取消/重试/恢复、输入快照、独立缓存及资源上限。
- CSV/JSON/HTML 和含音频 ZIP 导出，固定模型修订与可复现实测记录。
- 开源项目文档、许可证、贡献指南、Issue/PR 模板及基础 CI。

### Changed

- 默认服务端口改为 18763，前端开发端口改为 18764。

- 使用官方 npm registry、Node.js 22 LTS 及更新后的 Vite 修复版本。
- 更新核心 Web/上传/测试依赖及模型 extra 的 protobuf、sentencepiece 补丁。
- 记录仍需后续迁移的 Transformers 研究依赖通告与 SongEval 许可冲突。
