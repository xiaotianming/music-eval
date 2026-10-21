"""One metric per isolated subprocess; stdout is a single JSON envelope."""
import contextlib
import json
import os
import sys
import time
import traceback


def main():
    payload = json.load(sys.stdin)
    options = payload["options"]
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HF_HOME"] = options["model_cache"]
    os.environ["HF_HUB_OFFLINE"] = "1" if options["offline"] else "0"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["WANDB_MODE"] = "disabled"
    os.environ["WANDB_DISABLED"] = "true"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["OMP_NUM_THREADS"] = str(options["threads"])
    os.environ["MKL_NUM_THREADS"] = str(options["threads"])
    start = time.perf_counter()
    if "models" in payload:
        from .config import MODELS
        MODELS.update(payload["models"])
    from .metrics import Unavailable
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from .metrics import basic, clap, translate, songeval, fad
            metric = payload["metric"]
            sample = payload["sample"]
            if metric == "basic":
                value = basic(sample["path"])
            elif metric == "clap":
                value = clap(sample, options)
            elif metric == "translation":
                value = translate(sample["prompt"], options)
            elif metric == "songeval":
                value = songeval(sample, options, payload.get("exploratory", False))
            elif metric == "fad":
                value = fad(payload["samples"], payload["references"], options)
            else:
                raise ValueError("未知指标")
        result = {"status": "success", "value": value}
    except Unavailable as e:
        result = {"status": "skipped", "reason": str(e)}
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        result = {"status": "failed", "reason": f"{type(e).__name__}: {e}"}
    result["elapsed"] = time.perf_counter() - start
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
