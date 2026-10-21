# Music Eval · CPU 音乐评估工作台

[English quick start](README.en.md)

本地中文网页应用，用于导入 AI 生成音乐、单曲评估、同提示词作品对比、多模型统计及可选盲听。音频和提示词保留在本机，不调用云端评估或生成服务。

**状态：0.1.0 开发版本。** 原创代码采用 [MIT](LICENSE)；可选模型、第三方依赖及音乐资产各有独立许可，尤其是 SongEval 的上游许可声明存在不一致，详见 [第三方说明](THIRD_PARTY_NOTICES.md)。完整模型栈目前以 Windows 为已实测平台。

研究模型栈中的旧版 Transformers 仍有已知依赖通告，尚未完成大版本迁移；详见 [安全状态](docs/security-status.md)。本地研究应用不应直接对公网部署。

## 能做什么

- 导入已有生成结果，以提示词、模型版本和 seed 组织样本。
- 在 CPU 上运行基础音频检查、CLAP、本地中文翻译、SongEval 和可选参考集 FAD。
- 并排试听 2–4 首同提示词作品，按需开启匿名 A/B 投票。
- 逐项展示有效分数、失败原因、分布和配对差异，不生成未经校准的综合总分。
- 模型修订固定、任务可恢复、缓存可追溯，结果可导出 CSV/JSON/HTML/音频 ZIP。

本项目不生成音乐，不包含云端评估服务，也不以自动指标代替主观听感。

## 启动（Windows PowerShell）

先克隆实际仓库并进入项目根目录。需要已安装 Git、[uv](https://docs.astral.sh/uv/) 和 Node.js 22 LTS（见 `.node-version`）。安装脚本在项目内创建 Python 3.11 环境，不依赖系统 Python 版本；FFmpeg 使用 `imageio-ffmpeg` 自带的可执行文件。

```powershell
# 安装网页、基础评估及测试依赖
./scripts/setup.ps1
# 或使用这一条，同时安装 CPU CLAP 与本地翻译依赖
./scripts/setup.ps1 -Models
# SongEval 与 FAD 各使用独立 Python 环境
./scripts/setup-songeval.ps1
./scripts/setup-fad.ps1
# 下载固定修订的模型；可按需选择名称
./.venv/Scripts/python.exe scripts/download_models.py clap translation muq fad_clap roberta
# 启动
./scripts/start.ps1
```

打开 <http://127.0.0.1:8000>，API 文档在 <http://127.0.0.1:8000/docs>。默认仅本机访问。首次模型下载需要网络；离线前先完成模型预下载和一次所需指标推理，随后在运行设置开启离线模式。FAD 也需要固定的 RoBERTa 配置和分词器，因此预下载命令中包含 `roberta`，但不会另下载 RoBERTa 模型权重。

无需安装所有模型即可体验基础检查、对比和导出。建议先运行 `setup.ps1`、`start.ps1`，在网页点击“载入流程示例”；需要真实语义或美学评分时再安装相应模型环境。当前安装脚本按 Windows 编写，Linux 的核心测试 CI 不代表完整模型栈跨平台支持。

## 文档导航

| 文档 | 内容 |
|---|---|
| [评估协议](docs/protocol.md) | 分窗、预处理、统计和指标解释边界 |
| [依赖与复现](docs/dependencies.md) | 三个 Python 环境、CPU 依赖、锁文件更新和离线模型 |
| [架构](docs/architecture.md) | 数据流、任务与缓存、评估器扩展 |
| [HTTP API](docs/api.md) | 导入清单、任务、状态、报告及接口示例 |
| [实测验收](docs/validation.md) | 原始 CPU 基准与真实模型验证，保留其测试日期 |
| [贡献指南](CONTRIBUTING.md) | 本地开发、测试和 Pull Request |
| [安全说明](SECURITY.md) | 本地部署边界与漏洞报告方式 |
| [第三方说明](THIRD_PARTY_NOTICES.md) | 代码、模型和音频的许可边界 |
| [发布准备](docs/releasing.md) | 公开仓库与版本发布检查 |
| [更新记录](CHANGELOG.md) | 尚未发布与已发布版本变化 |

## 使用流程

1. 导入 WAV、FLAC、MP3，以及提示词、模型名、版本、音乐类型。支持 CSV/JSONL 批量清单，模板可在网页下载。同次上传文件名不可重复；清单 `audio` 字段必须与上传文件名一一对应，所有元数据校验通过后才发布该批数据。
2. 同一测试条件使用同一个 `prompt_id`。不同模型可以各生成多个 seed；系统先在提示词内平均，再对提示词等权平均，避免多生成的提示词被过度加权。请保持同组的提示词、目标时长及生成条件一致。
3. 选择音频，运行基础检查、CLAP、SongEval。纯音乐默认跳过 SongEval；可选择开启探索性四维评分。人声自然度始终不适用于纯音乐。
4. 在作品对比页选择同提示词的 2–4 首作品，单路播放并切换到相同时间位置。可选试听响度对齐仅创建播放副本，不改变评估输入。音乐段落不做自动对齐。
5. 查看模型报告：按模型、版本、类型、标签筛选；查看分布、成功率、共同提示词差异和 95% bootstrap 区间。可选匿名 A/B 投票，投票后揭晓；这不是 ABX 听辨实验。
6. 导出 CSV、JSON、HTML，或含配套音频的 ZIP。默认报告不嵌入音频。

资料库的“载入流程示例”生成四个简单合成和弦，明确标为 **synthetic**；仅用于验证软件操作，不能据此得出生成模型质量结论。

## 指标如何解释

| 指标 | 实现 | 边界 |
|---|---|---|
| 基础检查 | 100ms 分块 RMS 低于 −60 dBFS 视作静音；绝对幅度 ≥0.999 为近满幅；BS.1770 综合响度；NaN/Inf 检查 | 近满幅不必然代表削波；静音可能属于编曲；不输出“音质总分” |
| CLAP | `laion/larger_clap_music`，48kHz 单声道，连续 10 秒窗，尾段零填充，按有效时长加权 | 余弦相似度，不是指令完成率；歌词、否定条件、精确结构仍需人工判断 |
| 中文翻译 | `Helsinki-NLP/opus-mt-zh-en`，本地 CPU；保留原文及可编辑英文文本 | 中文文本按 token 分段，避免静默截断；音乐术语可能译错，应检查译文 |
| SongEval | 固定上游代码与权重，24kHz 单声道，全曲 MuQ hidden state 6 → Generator | 非商业用途；训练面向歌曲；纯音乐四维仅供探索；长曲可能耗时或超内存 |
| FAD | 固定 `fadtk/clap-laion-music`，48kHz，10 秒窗口、1 秒 hop，独立嵌入缓存 | 集合指标；需匹配场景的真实参考库；不与 CLAP 提示词评分共用嵌入，不跨协议比较 |

FAD 按模型版本和音乐类型分组，并只使用相同音乐类型的已选参考音频。用户需要用标签选择匹配的风格、语言与目标时长。系统阻止生成集和参考集出现相同音频哈希，但不声称可检测其他形式的数据污染。每组至少两首只是计算下限，**不是统计充分性的保证**；无通用“合格线”。第一版报告有限样本 FAD，不冒充 FAD∞。

长英文 CLAP 文本按模型容量分段，使用按 token 数加权后的文本嵌入归一化；报告保存分段数。这是本系统的长提示词协议，不能和采用截断文本的论文数字直接比较。

## 任务、缓存与资源

- SQLite WAL 持久保存任务、逐项状态、输入快照与结果。重启恢复排队/运行中任务；已完成项不重跑；取消会终止当前推理进程树。
- 单个推理子进程串行运行，每项结束后释放内存；默认 6 个 CPU 线程、batch size 1、单项 1800 秒、内存上限 22GB。资源限制可在网页调整，超限仅使当前指标失败。
- 任务使用创建时的输入快照。编辑提示词或译文后，旧 CLAP 结果显示“需要重算”；基础检查和美学不受译文影响。CLAP 音频嵌入与文本结果分开缓存。
- 重试只重排失败/跳过/取消项，保留原始任务快照并采用最新资源设置。**若修改输入，请新建任务**；重试不会偷偷更换输入。
- 原始音频从不截短，SongEval 不使用片段均值替代整曲结构评分。
- `data/tasks/<item_id>/worker.log` 保存子进程诊断；报告保存输入哈希、模型修订、协议、硬件、耗时与采样到的峰值内存。峰值是轮询测量，可能漏掉极短瞬态。

## 数据与开发

`data/` 保存 SQLite、原音频、衍生试听文件、缓存与模型，不进入 Git。`vendor/` 保存固定修订的 SongEval 源码和权重。可通过启动前设置 `MUSIC_EVAL_DATA` 更换数据根目录。备份时先停止服务，再备份整个数据目录。

```powershell
./.venv/Scripts/python.exe -m pytest -q
cd frontend
npm ci
npm run build
npm run dev   # Vite 5173，代理到后端 8000
```

主环境的依赖和模型版本分别锁定在 `uv.lock`、`models.lock.json`；独立环境使用两个 `requirements-*.lock`，CPU torch/torchaudio/torchvision 版本在安装脚本中固定。`fadtk` 需要 NumPy 1.x，因此不能直接装进主环境。

性能复现：

```powershell
./.venv/Scripts/python.exe scripts/benchmark.py --metrics basic --output docs/benchmark-basic.json
./.venv/Scripts/python.exe scripts/benchmark.py --metrics clap --output docs/benchmark-clap.json
./.venv/Scripts/python.exe scripts/benchmark.py --metrics songeval --output docs/benchmark-songeval.json
```

基准使用 30/180/300 秒合成和弦，测试性能而非音乐质量。每轮是新进程；CLAP 第二轮复用音频嵌入，因此与常驻模型热推理不同。结果不提供通用 CPU 速度保证。详细验收见 [docs/validation.md](docs/validation.md)。

## 方法与许可来源

- [SongEval 官方项目](https://github.com/ASLP-lab/SongEval)：README 声明 CC BY-NC-SA 4.0，但 LICENSE 文件为 Apache-2.0；未澄清前按非商业研究用途集成。
- [LAION CLAP 官方项目](https://github.com/LAION-AI/CLAP)、[音乐模型卡](https://huggingface.co/laion/larger_clap_music)。
- [OPUS 中文到英文模型卡](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en)：CC BY 4.0。
- [FADtk](https://github.com/microsoft/fadtk)、[Adapting Frechet Audio Distance for Generative Music Evaluation](https://arxiv.org/abs/2311.01616)：参考集、嵌入及样本量决定解释范围。
- [Benchmarking Music Generation Models and Metrics via Human Preference Studies](https://arxiv.org/abs/2506.19085)：自动指标应与人工偏好分开检验。

本仓库原创代码采用 MIT。当前模型评估配置面向非商业研究；第三方代码、权重和参考音乐各保留其原有许可，不能由本项目的 MIT 授权推断模型或音乐素材的商业使用权。
