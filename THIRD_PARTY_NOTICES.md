# 第三方组件与许可边界

本仓库原创适配代码、网页及文档使用 [MIT](LICENSE)。这不重新许可第三方软件、模型权重、训练数据、生成音乐或参考音频。包管理器安装的第三方项目各自保留版权和许可证；锁文件是版本记录，不是完整法律审查。

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

两者不一致，不能据此推断代码、权重和示例音频均可商用。Music Eval 暂将 SongEval 集成限定为非商业研究，不复制其模型实现或权重进本仓库。商业使用或再分发之前，应向上游确认各类资产的适用许可。运行结果中的许可字段沿用上游 README 的研究用途声明，不是对该冲突的法律裁定。

## 音频与实测记录

网页内置流程示例由本项目生成简单合成和弦，不是来自真实模型的质量样本。`docs/*smoke.json` 的数字用于推理验收；其中 SongEval 使用了上游示例音频，但记录只含指标、时长和哈希，音频文件不提交本仓库。

用户导入的音频、真实参考库、导出结果以及运行缓存均属于用户本机数据，不会因使用 Music Eval 自动获得公开再分发授权。音乐生成评估相关论文的引用见 README 与评估协议。
