"""Measure real subprocess inference, not subjective quality of synthetic audio."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import psutil
import soundfile as sf
from backend.config import DATA, ROOT, MODELS, settings
from backend.metrics import fingerprint


def measure(metric, sample, options):
    payload = {"metric": metric, "sample": sample, "options": options, "exploratory": False}
    interpreter = options["songeval_python"] if metric == "songeval" else sys.executable
    dest = DATA / "benchmark" / metric
    dest.mkdir(exist_ok=True, parents=True)
    start = time.perf_counter()
    peak = 0
    with (dest / "out.json").open("w", encoding="utf-8") as out, (dest / "worker.log").open("w", encoding="utf-8") as err:
        p = subprocess.Popen([interpreter, "-m", "backend.worker"], cwd=ROOT, stdin=subprocess.PIPE,
                             stdout=out, stderr=err, text=True, encoding="utf-8",
                             env={**os.environ,"PYTHONIOENCODING":"utf-8"})
        p.stdin.write(json.dumps(payload))
        p.stdin.close()
        while p.poll() is None:
            try:
                peak = max(peak, sum(q.memory_info().rss for q in [psutil.Process(p.pid), *psutil.Process(p.pid).children(recursive=True)]) / 2**20)
            except psutil.Error:
                pass
            if time.perf_counter() - start > options["timeout_seconds"] or peak > options["memory_limit_gb"] * 1024:
                from backend.jobs import stop_tree
                stop_tree(p)
                return {"status":"resource_limit", "seconds":time.perf_counter()-start,"peak_mb":peak}
            time.sleep(.1)
    try:
        result = json.loads((dest / "out.json").read_text(encoding="utf-8"))
    except ValueError:
        result = {"status":"failed","reason":"See data/benchmark/worker.log"}
    return {"status":result["status"],"reason":result.get("reason"),"seconds":time.perf_counter()-start,"peak_mb":peak}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", nargs="+", default=["basic"], choices=["basic","clap","songeval"])
    parser.add_argument("--durations", nargs="+", type=int, default=[30,180,300])
    parser.add_argument("--output", default="docs/benchmark.json")
    args = parser.parse_args()
    results=[]
    for seconds in args.durations:
        sr=24000
        t=np.arange(sr*seconds)/sr
        # Synthetic input is deliberately not described as generated music.
        x=.06*(np.sin(2*np.pi*261.63*t)+np.sin(2*np.pi*329.63*t)+np.sin(2*np.pi*392*t))
        path=DATA/'audio'/f'benchmark-synthetic-{seconds}.wav'
        sf.write(path,x,sr)
        sample={"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"prompt":"A sustained synthetic chord",
                "prompt_en":"A sustained synthetic chord","audio_type":"song"}
        for metric in args.metrics:
            for run in ("first_process","repeat_process"):
                cache = DATA / "cache" / ("clap-audio-" + fingerprint({"sha256":sample["sha256"],"model":MODELS["clap"],
                        "protocol":"music-eval-v1.0","sr":48000,"window":10,"hop":10,"tail":"zero_pad"}) + ".npz")
                if metric == "clap" and run == "first_process":
                    cache.unlink(missing_ok=True)  # Only this synthetic benchmark's regenerable embedding.
                row={"duration_seconds":seconds,"metric":metric,"run":run,"audio_embedding_cache_before":cache.exists() if metric == "clap" else None,
                     **measure(metric,sample,settings())}
                results.append(row)
                print(json.dumps(row),flush=True)
    out=ROOT/args.output
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps({"hardware":{"platform":platform.platform(),"processor":platform.processor(),"cpus":os.cpu_count(),"ram_gb":psutil.virtual_memory().total/2**30},
                               "models":MODELS,"input":"synthetic chord; performance only, not quality validation",
                               "run_definition":"Fresh worker per run; first CLAP run removes this synthetic input's embedding cache, repeat reuses embeddings. Not an OS cold-cache benchmark. Download time excluded when predownloaded.",
                               "measurements":results},ensure_ascii=False,indent=2),encoding='utf-8')
