import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MUSIC_EVAL_DATA", ROOT / "data")).resolve()
for name in ("audio", "cache", "tasks", "models", "exports"):
    (DATA / name).mkdir(parents=True, exist_ok=True)
DB = DATA / "music_eval.sqlite3"
PROTOCOL = "music-eval-v1.0"
MODELS = {
    "clap": {"id": "laion/larger_clap_music", "revision": "main"},
    "translation": {"id": "Helsinki-NLP/opus-mt-zh-en", "revision": "main"},
    "muq": {"id": "OpenMuQ/MuQ-large-msd-iter", "revision": "main"},
}
lock = ROOT / "models.lock.json"
if lock.exists():
    MODELS.update(json.loads(lock.read_text(encoding="utf-8")))


def settings():
    p = DATA / "settings.json"
    defaults = {"offline": False, "threads": 6, "timeout_seconds": 1800,
                "memory_limit_gb": 22, "model_cache": str(DATA / "models"),
                "songeval_python": str(ROOT / ".venv-songeval" / "Scripts" / "python.exe"),
                "songeval_dir": str(ROOT / "vendor" / "SongEval")}
    if p.exists():
        defaults.update(json.loads(p.read_text(encoding="utf-8")))
    return defaults
