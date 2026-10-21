import csv
import html
import io
import itertools
import json
from collections import defaultdict
import numpy as np
from . import db
from .jobs import signature
from .config import MODELS, PROTOCOL


def latest_results(sample):
    out = {}
    for row in db.rows("SELECT * FROM items WHERE sample_id=? ORDER BY rowid DESC", (sample["id"],)):
        metric = row["metric"]
        if metric in out or metric == "fad":
            continue
        item = db.decode_item(row)
        item["stale"] = item["snapshot"]["signature"] != signature(sample, metric)
        out[metric] = item
    return out


def numeric_metrics(results):
    out = {}
    for metric, item in results.items():
        if item["status"] != "success" or item["stale"]:
            continue
        v = item["result"]["value"]
        if metric == "basic":
            for k in ("silence_ratio", "near_full_scale_ratio", "loudness_lufs", "duration"):
                if v[k] is not None:
                    out[k] = v[k]
        elif metric == "clap":
            out["clap"] = v["score"]
        elif metric == "songeval":
            out.update({k: x for k, x in v["scores"].items() if x is not None})
    return out


def report(samples):
    records, groups = [], defaultdict(list)
    for s in samples:
        if s["role"] != "generated":
            continue
        results = latest_results(s)
        record = {"sample": {k: v for k, v in s.items() if k != "path"}, "results": results,
                  "metrics": numeric_metrics(results)}
        records.append(record)
        groups[(s["model_id"], s["model_version"], s["audio_type"])].append(record)
    summary, prompt_means = [], {}
    for group, records_g in sorted(groups.items()):
        buckets = defaultdict(lambda: defaultdict(list))
        for r in records_g:
            for k, v in r["metrics"].items():
                buckets[k][r["sample"]["prompt_id"]].append(v)
        pm = {k: {p: float(np.mean(v)) for p, v in ps.items()} for k, ps in buckets.items()}
        prompt_means[group] = pm
        metrics = {}
        for k, values in pm.items():
            vs = list(values.values())
            metrics[k] = {"mean": float(np.mean(vs)), "median": float(np.median(vs)),
                          "p10": float(np.quantile(vs, .1)), "p90": float(np.quantile(vs, .9)),
                          "prompt_count": len(vs), "values": vs}
        statuses = defaultdict(lambda: defaultdict(int))
        for r in records_g:
            for k, it in r["results"].items():
                statuses[k]["stale" if it["stale"] else it["status"]] += 1
        summary.append({"group": list(group), "count": len(records_g), "metrics": metrics,
                        "statuses": statuses, "prompt_count": len({r["sample"]["prompt_id"] for r in records_g})})
    pairs = []
    rng = np.random.default_rng(2026)
    for ga, gb in itertools.combinations(prompt_means, 2):
        if ga[2] != gb[2]:
            continue
        for metric in sorted(prompt_means[ga].keys() & prompt_means[gb].keys()):
            a, b = prompt_means[ga][metric], prompt_means[gb][metric]
            shared = sorted(a.keys() & b.keys())
            if not shared:
                continue
            delta = np.array([a[p] - b[p] for p in shared])
            ci = None
            if len(shared) >= 2:
                boot = np.mean(delta[rng.integers(0, len(delta), size=(2000, len(delta)))], axis=1)
                ci = [float(x) for x in np.quantile(boot, [.025, .975])]
            pairs.append({"a": ga, "b": gb, "metric": metric, "shared_prompts": len(shared),
                          "delta_a_minus_b": float(np.mean(delta)), "ci95": ci,
                          "warning": "共同提示词不足 20，区间仅供探索" if len(shared) < 20 else None})
    correlations = []
    aesthetic = ["Coherence", "Musicality", "Memorability", "Clarity", "Naturalness"]
    for a, b in itertools.combinations(aesthetic, 2):
        points = [(r["metrics"][a], r["metrics"][b]) for r in records if a in r["metrics"] and b in r["metrics"]]
        if len(points) >= 3:
            arr = np.array(points)
            if np.all(np.std(arr, axis=0) > 0):
                correlations.append({"a": a, "b": b, "n": len(points), "pearson": float(np.corrcoef(arr.T)[0, 1])})
    fad = []
    selected_ids = {s["id"] for s in samples}
    seen = set()
    for row in db.rows("SELECT * FROM items WHERE metric='fad' ORDER BY rowid DESC"):
        it = db.decode_item(row)
        ss = it["snapshot"].get("samples", [])
        key = tuple(it["snapshot"].get("group", []))
        if ss and all(s["id"] in selected_ids for s in ss) and key not in seen:
            current = [s for s in samples if (s["model_id"], s["model_version"], s["audio_type"]) == key and s["role"] == "generated"]
            it["stale"] = ({s["id"] for s in ss} != {s["id"] for s in current}
                           or any(it["snapshot"]["signature"].get(k) != signature(ss[0], "fad").get(k)
                                  for k in ("model", "checkpoint", "text_architecture", "protocol")))
            fad.append(it)
            seen.add(key)
    return {"protocol": PROTOCOL, "models": MODELS, "records": records, "groups": summary,
            "pairs": pairs, "correlations": correlations, "fad": fad,
            "notes": ["CLAP 为语义相关程度，不是指令完成百分比。", "FAD 仅比较集合；不同协议分数不能混比。",
                      "先在提示词内汇总，再等权汇总提示词；不生成综合总分。"]}


def export_csv(data):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["sample_id", "filename", "model_id", "model_version", "prompt_id", "metric", "status", "value", "reason", "sha256"])
    for r in data["records"]:
        s = r["sample"]
        for metric, it in r["results"].items():
            writer.writerow([s["id"], s["filename"], s["model_id"], s["model_version"], s["prompt_id"], metric,
                             "stale" if it["stale"] else it["status"], json.dumps(it["result"], ensure_ascii=False), it["reason"], s["sha256"]])
    for it in data["fad"]:
        writer.writerow(["", "", *it["snapshot"]["group"][:2], "", "fad", it["status"], json.dumps(it["result"], ensure_ascii=False), it["reason"], ""])
    return "\ufeff" + output.getvalue()


def export_html(data):
    escape = html.escape
    body = []
    for g in data["groups"]:
        body.append(f"<h2>{escape(' / '.join(g['group']))}</h2><p>{g['count']} 首 · {g['prompt_count']} 个提示词</p><table><tr><th>指标</th><th>提示词等权均值</th><th>P10–P90</th></tr>")
        for k, v in g["metrics"].items():
            body.append(f"<tr><td>{escape(k)}</td><td>{v['mean']:.4f}</td><td>{v['p10']:.4f} – {v['p90']:.4f}</td></tr>")
        body.append("</table>")
    detail = escape(json.dumps(data, indent=2, ensure_ascii=False))
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>音乐评估报告</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#182526}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#176b58}</style><h1>CPU 音乐评估报告</h1><p>' + escape(' '.join(data["notes"])) + '</p>' + ''.join(body) + '<details><summary>完整结果、配对统计、协议与输入哈希</summary><pre>' + detail + '</pre></details></html>'
