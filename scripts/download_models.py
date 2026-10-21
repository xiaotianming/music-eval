"""Pre-download pinned models for offline use; never sends audio or prompts."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import MODELS, settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", default=["clap", "translation"], choices=["clap", "translation", "muq", "fad_clap", "roberta"])
    args = parser.parse_args()
    os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "1800"
    os.environ["HF_HUB_ETAG_TIMEOUT"] = "60"
    from huggingface_hub import snapshot_download
    from backend.hub import configure_hub
    configure_hub()
    for name in args.models:
        spec = MODELS[name]
        patterns = ["*.json", "*.txt", "*.model", "*.spm", "*.safetensors", "pytorch_model.bin"]
        if name == "fad_clap":
            patterns = ["music_audioset_epoch_15_esc_90.14.pt"]
        elif name in ("clap", "translation"):
            patterns = ["*.json", "*.txt", "*.model", "*.spm", "pytorch_model.bin"]
        elif name == "roberta":
            patterns = ["config.json", "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt", "special_tokens_map.json"]
        path = snapshot_download(spec["id"], revision=spec["revision"], cache_dir=settings()["model_cache"],
                                 allow_patterns=patterns, max_workers=2)
        print(name, spec["revision"], path, flush=True)
