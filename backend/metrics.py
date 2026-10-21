"""Model adapters. This module is imported only in the supervised CPU worker."""
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from .audio import mono_resample, windows, basic
from .config import DATA, MODELS, PROTOCOL


class Unavailable(Exception):
    pass


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepare_torch(options):
    try:
        import torch
    except ImportError as e:
        raise Unavailable("尚未安装模型依赖，请运行 scripts/setup.ps1 -Models") from e
    torch.set_num_threads(options["threads"])
    from .hub import configure_hub
    configure_hub()
    torch.manual_seed(0)
    torch.set_grad_enabled(False)
    return torch


def model_args(kind, options):
    return {"revision": MODELS[kind]["revision"], "cache_dir": options["model_cache"],
            "local_files_only": options["offline"]}


def token_chunks(text, tokenizer, limit):
    # Token-based segmentation retains all text. Never use truncation=True.
    ids = tokenizer.encode(text, add_special_tokens=False)
    return [(tokenizer.decode(ids[i:i + limit], skip_special_tokens=True), len(ids[i:i + limit]))
            for i in range(0, len(ids), limit)]


def translate(text, options):
    if not text.strip():
        return {"text": "", "source": "missing"}
    if not re.search(r"[\u3400-\u9fff]", text):
        return {"text": text, "source": "original_en"}
    prepare_torch(options)
    from transformers import MarianMTModel, MarianTokenizer
    spec = MODELS["translation"]
    kwargs = model_args("translation", options)
    tokenizer = MarianTokenizer.from_pretrained(spec["id"], **kwargs)
    model = MarianMTModel.from_pretrained(spec["id"], use_safetensors=False, **kwargs).to("cpu").eval()
    parts = token_chunks(text, tokenizer, 240)
    output = []
    for part, _ in parts:
        batch = tokenizer(part, return_tensors="pt", truncation=False)
        ids = model.generate(**batch, max_new_tokens=480, num_beams=4)
        # Forced EOS can mask hitting the generation budget. Treat the budget
        # boundary itself as failure rather than accepting a truncated sentence.
        if len(ids[0]) >= 481:
            raise ValueError("翻译输出达到长度上限，请缩短提示词或手动提供英文译文")
        output.append(tokenizer.decode(ids[0], skip_special_tokens=True))
    return {"text": " ".join(output), "source": "local", "model": spec, "segments": len(parts)}


def clap(sample, options):
    torch = prepare_torch(options)
    translated = None
    text = sample.get("prompt_en", "").strip()
    if not text:
        translated = translate(sample.get("prompt", ""), options)
        text = translated["text"]
    if not text:
        raise Unavailable("缺少提示词，无法计算语义匹配")
    from transformers import ClapModel, ClapProcessor
    spec = MODELS["clap"]
    kwargs = model_args("clap", options)
    processor = ClapProcessor.from_pretrained(spec["id"], **kwargs)
    model = ClapModel.from_pretrained(spec["id"], use_safetensors=False, **kwargs).to("cpu").eval()
    identity = {"sha256": sample["sha256"], "model": spec, "protocol": PROTOCOL,
                "sr": 48000, "window": 10, "hop": 10, "tail": "zero_pad"}
    cache = DATA / "cache" / ("clap-audio-" + fingerprint(identity) + ".npz")
    if cache.exists():
        with np.load(cache) as z:
            audio_features, starts, lengths = z["features"], z["starts"], z["lengths"]
    else:
        x = mono_resample(sample["path"], 48000)
        features, starts, lengths = [], [], []
        for start, valid, chunk in windows(x):
            inputs = processor(audios=chunk, sampling_rate=48000, return_tensors="pt")
            f = model.get_audio_features(**inputs)
            f = torch.nn.functional.normalize(f, dim=-1)
            features.append(f.cpu().numpy()[0])
            starts.append(start)
            lengths.append(valid)
        audio_features = np.array(features)
        temp = cache.with_suffix(".tmp")
        with temp.open("wb") as f:
            np.savez_compressed(f, features=audio_features, starts=starts, lengths=lengths)
        temp.replace(cache)
    tokenizer = processor.tokenizer
    max_tokens = min(int(model.config.text_config.max_position_embeddings) - 2, 75)
    parts = token_chunks(text, tokenizer, max_tokens)
    text_features, weights = [], []
    for part, weight in parts:
        inputs = processor(text=[part], return_tensors="pt", padding=True, truncation=False)
        f = model.get_text_features(**inputs)
        text_features.append(torch.nn.functional.normalize(f, dim=-1).cpu().numpy()[0])
        weights.append(weight)
    tf = np.average(text_features, axis=0, weights=weights)
    tf /= max(float(np.linalg.norm(tf)), 1e-12)
    scores = audio_features @ tf
    return {"score": float(np.average(scores, weights=lengths)), "text_used": text,
            "translation": translated, "text_segments": len(parts), "model": spec,
            "windows": [{"start": float(a), "valid_seconds": float(b), "score": float(c)}
                        for a, b, c in zip(starts, lengths, scores)], "audio_protocol": identity}


def songeval(sample, options, exploratory):
    if sample["audio_type"] == "instrumental" and not exploratory:
        raise Unavailable("纯音乐默认不运行 SongEval；可开启探索性四维评估")
    prepare_torch(options)
    import sys
    repo = Path(options["songeval_dir"])
    if not (repo / "ckpt/model.safetensors").exists():
        raise Unavailable("SongEval 权重缺失，请运行 scripts/setup-songeval.ps1")
    import subprocess
    rev = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(repo), "diff", "HEAD", "--exit-code", "--", "model.py", "config.yaml"], capture_output=True)
    if rev.returncode or rev.stdout.strip() != MODELS["songeval"]["revision"] or dirty.returncode:
        raise ValueError("SongEval 源码与锁定修订不符，请重新运行安装脚本或恢复源码")
    weight_hash = hashlib.sha256((repo / "ckpt/model.safetensors").read_bytes()).hexdigest()
    if weight_hash != MODELS["songeval"]["weights_sha256"]:
        raise ValueError("SongEval 权重校验失败")
    sys.path.insert(0, str(repo))
    from hydra.utils import instantiate
    from omegaconf import OmegaConf
    from safetensors.torch import load_file
    from muq import MuQ
    import torch
    import librosa
    x, _ = librosa.load(sample["path"], sr=24000)
    if not len(x) or not np.isfinite(x).all():
        raise ValueError("音频为空或包含 NaN/Inf")
    config = OmegaConf.load(repo / "config.yaml")
    model = instantiate(config.generator).to("cpu").eval()
    model.load_state_dict(load_file(str(repo / "ckpt/model.safetensors"), device="cpu"), strict=True)
    muq = MuQ.from_pretrained(MODELS["muq"]["id"], **model_args("muq", options)).to("cpu").eval()
    # Whole waveform, matching official inference: hidden state 6 -> Generator.
    hidden = muq(torch.from_numpy(x).unsqueeze(0), output_hidden_states=True)["hidden_states"][6]
    scores = model(hidden).squeeze(0).cpu().tolist()
    names = ["Coherence", "Musicality", "Memorability", "Clarity", "Naturalness"]
    values = dict(zip(names, map(float, scores)))
    if sample["audio_type"] == "instrumental":
        values["Naturalness"] = None
    return {"scores": values, "exploratory": sample["audio_type"] == "instrumental",
            "full_audio": True, "input_seconds": len(x) / 24000,
            "model": MODELS["songeval"], "muq": MODELS["muq"], "license": "CC BY-NC-SA 4.0"}


def fad(samples, references, options):
    if not references:
        raise Unavailable("缺少参考集；FAD 只能比较音频集合")
    if len(samples) < 2 or len(references) < 2:
        raise Unavailable("生成集与参考集各至少需要两首音频；小样本结果仍不稳定")
    torch = prepare_torch(options)
    try:
        from fadtk.model_loader import CLAPLaionModel, ModelLoader
        from fadtk.fad import calc_embd_statistics
    except ImportError as e:
        raise Unavailable("FAD 独立环境尚未安装，请运行 scripts/setup-fad.ps1") from e
    loader = None
    protocol = {"backend": "fadtk/clap-laion-music", "revision": MODELS["fadtk"]["revision"],
                "distance": "symmetric-psd-eigh-v1", "text_architecture": MODELS["roberta"],
                "checkpoint": "music_audioset_epoch_15_esc_90.14.pt", "checkpoint_revision": MODELS["fad_clap"], "sr": 48000,
                "window_seconds": 10, "hop_seconds": 1, "resampling": "scipy-resample-poly", "protocol": PROTOCOL}
    def embed(s):
        nonlocal loader
        identity = {**protocol, "sha256": s["sha256"]}
        dest = DATA / "cache" / ("fad-" + fingerprint(identity) + ".npy")
        x = mono_resample(s["path"], 48000)
        if dest.exists():
            return np.load(dest).astype(np.float64), len(x) / 48000
        if loader is None:
            from huggingface_hub import hf_hub_download
            # Bypass upstream's unversioned downloader: resolve a pinned asset in
            # the selected local cache, honoring offline mode before any network.
            checkpoint = hf_hub_download(MODELS["fad_clap"]["id"], protocol["checkpoint"],
                                         revision=MODELS["fad_clap"]["revision"],
                                         cache_dir=options["model_cache"], local_files_only=options["offline"])
            loader = CLAPLaionModel.__new__(CLAPLaionModel)
            ModelLoader.__init__(loader, "clap-laion-music", 512, 48000)
            loader.type = "music"
            loader.model_file = Path(checkpoint)
            loader.device = torch.device("cpu")
            # Upstream initializes RoBERTa from an unpinned pretrained download
            # before replacing ALL parameters from the CLAP checkpoint. Create
            # the same architecture from pinned config instead; strict upstream
            # load_state_dict still validates the complete final checkpoint.
            from transformers import RobertaConfig, RobertaModel, RobertaTokenizer
            from unittest.mock import patch
            roberta = MODELS["roberta"]
            args = {"revision": roberta["revision"], "cache_dir": options["model_cache"], "local_files_only": options["offline"]}
            text_config = RobertaConfig.from_pretrained(roberta["id"], **args)
            tokenizer = RobertaTokenizer.from_pretrained(roberta["id"], **args)
            with patch.object(RobertaModel, "from_pretrained", side_effect=lambda *a, **kw: RobertaModel(text_config)), \
                 patch.object(RobertaTokenizer, "from_pretrained", return_value=tokenizer):
                loader.load_model()
            loader.model.to("cpu").eval()
        # Use upstream windowing/quantization; keep separate from CLAP score cache.
        v = loader.get_embedding(x).astype(np.float64)
        temp = dest.with_suffix(".tmp")
        with temp.open("wb") as f:
            np.save(f, v)
        temp.replace(dest)
        return v, len(x) / 48000
    def collect(ss):
        out = [embed(s) for s in ss]
        return np.concatenate([v for v, _ in out]), sum(d for _, d in out)
    a, da = collect(samples)
    b, db = collect(references)
    from .distance import frechet_psd
    mean_a, cov_a = calc_embd_statistics(a)
    mean_b, cov_b = calc_embd_statistics(b)
    value = frechet_psd(mean_a, cov_a, mean_b, cov_b)
    if not np.isfinite(value) or value < -1e-4:
        raise ValueError("FAD 数值不稳定；请增加样本量并检查参考集")
    return {"score": max(0, value), "protocol": protocol, "generated_count": len(samples),
            "reference_count": len(references), "generated_seconds": da, "reference_seconds": db,
            "generated_windows": len(a), "reference_windows": len(b),
            "warning": "小样本或风格不匹配时结果不稳定；无通用合格线",
            "reference_metadata": [{k: s[k] for k in ("id", "sha256", "audio_type", "tags")} for s in references]}
