# 第三方组件与许可边界

[MIT](LICENSE) 适用于本仓库的原创代码、网页和文档。第三方软件、模型和音频按各自许可使用，依赖版本见锁文件。

## 主要上游

| 组件 | 来源 | 当前采用方式 |
|---|---|---|
| FastAPI / React / Vite 等基础软件 | Python 与 npm 官方软件包 | 由锁文件安装；保留各包自带许可 |
| 音乐 CLAP | [LAION 官方项目](https://github.com/LAION-AI/CLAP)、[模型卡](https://huggingface.co/laion/larger_clap_music) | 固定模型修订，本地下载；模型卡标注 Apache-2.0 |
| 中文翻译 | [Helsinki-NLP/opus-mt-zh-en](https://huggingface.co/Helsinki-NLP/opus-mt-zh-en) | 固定模型修订；模型卡标注 CC BY 4.0，应保留来源与署名 |
| MuQ | [OpenMuQ 模型卡](https://huggingface.co/OpenMuQ/MuQ-large-msd-iter) | 由 SongEval 独立环境加载；以具体模型卡及资产许可为准 |
| FADtk | [Microsoft FADtk](https://github.com/microsoft/fadtk) | 固定 Git 修订，独立安装；项目标注 MIT |
| 原 LAION checkpoint / RoBERTa | `models.lock.json` 中对应的官方模型仓库 | 只下载所需文件；以对应资产声明为准 |
| SongEval | [ASLP-lab/SongEval](https://github.com/ASLP-lab/SongEval) | 可选、独立源码目录，**不随本仓库分发** |

## SongEval 许可声明不一致

在本项目固定修订 `848fb2ff3a2a9d64dcb20d46f07238c28abd7add` 中：

- 根目录 `LICENSE` 文件是 Apache License 2.0。
- `README.md` 的 License 段却声明 CC BY-NC-SA 4.0 和仅非商业使用。

Music Eval 将 SongEval 作为非商业研究组件，源码和权重由安装脚本下载。商业使用或再分发前，需向上游确认代码、权重和示例音频各自的许可。结果中的许可字段沿用上游 README 的声明。

## 音频与实测记录

网页示例是本项目生成的简单和弦。`docs/*smoke.json` 保存推理检查的指标、时长和输入哈希，其中 SongEval 的输入来自上游示例音频。该音频随上游源码下载到 `vendor/`。

公开分享导出音频或参考库前，请确认素材的再分发权。相关评估论文的引用见 README 与评估协议。
