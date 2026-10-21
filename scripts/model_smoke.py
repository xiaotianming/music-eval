"""Real-model smoke tests. Run explicitly after installation/downloads."""
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.config import ROOT, DATA, settings
from backend.audio import read_audio
import hashlib


def run(metric, sample, **extra):
    options = settings()
    options["offline"] = True
    python = options["songeval_python"] if metric == "songeval" else str(ROOT / ".venv-fad/Scripts/python.exe") if metric == "fad" else sys.executable
    payload = {"metric":metric,"sample":sample,"options":options,**extra}
    p = subprocess.run([python,"-m","backend.worker"],input=json.dumps(payload),capture_output=True,text=True,encoding="utf-8",cwd=ROOT,
                       env={**os.environ,"PYTHONIOENCODING":"utf-8"},timeout=1800)
    try: result=json.loads(p.stdout)
    except ValueError: result={"status":"failed","reason":p.stderr[-3000:]}
    return result


if __name__ == "__main__":
    output={}
    path=ROOT/'vendor/SongEval/example/example.mp3'
    sample={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"prompt":"流行人声歌曲", "prompt_en":"A pop song with vocals", "audio_type":"song"}
    output["translation"]=run("translation",{**sample,"prompt":"悲伤的钢琴独奏，缓慢、柔和，没有鼓。"})
    output["songeval"]=run("songeval",sample)
    # Explicitly test pure-music applicability before loading a model.
    output["instrumental_default"]=run("songeval",{**sample,"audio_type":"instrumental"})
    output["input"]={"source":"SongEval upstream example; inference smoke only","sha256":sample["sha256"],"seconds":len(read_audio(path)[0])/read_audio(path)[1]}
    out=ROOT/'docs/model-smoke.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    for metric,result in output.items():
        print(metric,json.dumps(result,ensure_ascii=False),flush=True)
