# 安全策略

## 本地运行

Music Eval 面向本机单用户，监听 `127.0.0.1`。服务没有公网身份认证和多租户隔离，请保留本地访问配置。

音频、提示词、SQLite、缓存和任务日志保存在 `data/` 或 `MUSIC_EVAL_DATA` 指定的目录。分享报告前检查其中的提示词、文件名和本机路径；ZIP 导出还包含音频。环境变量需在启动前设置，`.env` 文件不会自动加载。

## 报告漏洞

优先通过 GitHub 仓库的 **Security → Advisories → Report a vulnerability** 私密报告。若该入口尚未启用，可提交一条请求私密联系方式的 Issue，漏洞细节和凭据留到私密渠道提供。

报告请包含受影响版本、平台、最小复现和影响。0.x 阶段优先在最新开发版本修复问题。

## 已知依赖问题

模型栈固定的 `transformers==4.51.3` 有多项公开安全通告，版本迁移及复现审计的方法见 [安全状态](docs/security-status.md)。使用 `models.lock.json` 指定来源的模型资产；发布前按 [发布流程](docs/releasing.md) 检查依赖。
