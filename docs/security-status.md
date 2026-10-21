# 依赖安全状态

检查日期：2026-10-21。该记录描述本次维护时可复现的检查，不代表永久安全保证。

## 本次修复

- Vite 从 6.3.5 更新至 6.4.5，官方 npm registry 的 `npm audit` 报告零已知漏洞。
- 更新 FastAPI、Starlette、python-multipart 和 pytest，处理旧 Web/上传/开发依赖的公开通告。主环境为 Starlette 设置安全版本下限并通过 `uv.lock` 固定实际版本。
- 更新模型 extra 的 protobuf 至 5.29.6、sentencepiece 至 0.2.1；没有随文档维护改变音乐权重或评分协议。

更新后不含 `models` extra 的核心 + 测试依赖，通过从 `uv.lock` 导出完整精确版本再运行 `pip-audit`，报告零已知漏洞；实际锁定 FastAPI 0.156.8、Starlette 1.9.0、python-multipart 0.0.32、pytest 9.1.1。包含模型 extra 的主环境仍报告 Transformers 通告，不能把核心审计结果套用到它。

## 尚未解决的研究模型栈事项

主环境可选 `models` extra、SongEval 环境和 FAD 环境继续使用 `transformers==4.51.3`，以保留已验证的 CLAP、MuQ、LAION 后端兼容性。该版本被 `pip-audit` 报告多项漏洞，包括部分 checkpoint 转换器、其他模型的反序列化或配置加载路径，以及自定义生成模块加载路径。

本项目只使用固定模型修订，不提供任意 checkpoint 转换或模型仓库输入功能，但这**不等于这些通告已修复或全部不可利用**。没有进行逐项可利用性裁定；不要把相关环境当作处理任意不可信模型的沙箱，也不要宣称可选模型栈安全审计已通过。

迁移 Transformers 大版本会影响 API 返回类型、MuQ 和 LAION 兼容性，需作为独立变更处理：完成加载适配、模型分数与缓存协议核对、离线推理回归及资源基准后再更新三套锁文件。不能仅用审计忽略列表掩盖旧版本。

两个上游独立环境目前保留原有冻结版本；除主环境补丁之外，未对其所有传递依赖作全面安全升级或零漏洞承诺。

## 复现审计

```powershell
# 前端
cd frontend
npm audit --registry=https://registry.npmjs.org
cd ..
# 主环境，包括已安装的可选模型依赖
uvx pip-audit --path .venv/Lib/site-packages
# 两个独立环境
uvx pip-audit --path .venv-songeval/Lib/site-packages
uvx pip-audit --path .venv-fad/Lib/site-packages
```

不安装 `models` extra 的核心依赖应另外审计，避免把核心 Web 栈的结果与研究模型栈混为一谈。CI 只做不下载模型的测试与前端审计，不能代替这些可选检查。

核心审计的复现方式（先创建已被 Git 忽略的 `.cache` 目录）：

```powershell
New-Item -ItemType Directory -Force .cache | Out-Null
uv export --locked --extra dev --no-hashes --output-file .cache/core-requirements.txt
uvx pip-audit -r .cache/core-requirements.txt --no-deps --disable-pip
```

这里的 `--no-deps` 仅因为 uv 已导出完整传递依赖集合，不是忽略传递依赖的检查。
