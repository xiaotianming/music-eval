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
from .scoring import overall_score


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


def scored_record(sample, results):
    overall = overall_score(results, sample["audio_type"])
    metrics = numeric_metrics(results)
    if overall["status"] == "complete" and overall["score"] is not None:
        metrics["overall_score"] = overall["score"]
    return {"sample": {k: v for k, v in sample.items() if k != "path"}, "results": results,
            "metrics": metrics, "overall": overall}


def sample_report(sample, job_id=None):
    """Read a song's latest results or the immutable results of one task."""
    job = None
    if job_id:
        job = db.one("SELECT id,status,created FROM jobs WHERE id=?", (job_id,))
        items = db.rows("SELECT * FROM items WHERE job_id=? AND sample_id=? AND metric!='fad' ORDER BY rowid",
                        (job_id, sample["id"]))
        if not job or not items:
            raise ValueError("该任务中没有这首音频的单曲评估记录")
        decoded = [db.decode_item(it) for it in items]
        sample = decoded[0]["snapshot"]["sample"]
        results = {it["metric"]: {**it, "stale": False} for it in decoded}
    else:
        results = latest_results(sample)
    return {**scored_record(sample, results), "job": job, "protocol": PROTOCOL}


METRIC_LABELS = {"overall_score": "综合评分（100分）", "basic": "基础检查", "clap": "提示词匹配", "songeval": "歌曲美学", "translation": "本地翻译",
                 "clap_score": "CLAP 相似度", "silence_ratio": "静音比例", "near_full_scale_ratio": "近满幅比例",
                 "loudness_lufs": "综合响度 LUFS", "duration": "时长（秒）", "Coherence": "整体连贯性",
                 "Musicality": "音乐性", "Memorability": "记忆度", "Clarity": "结构清晰度", "Naturalness": "人声自然度"}


def song_html(record):
    esc = html.escape
    s, results = record["sample"], record["results"]
    text = [f'<section><h2>{esc(s["filename"])}</h2>',
            f'<p>模型：{esc(s["model_id"])} / {esc(s["model_version"])} · 提示词：{esc(s["prompt_id"])}</p>',
            f'<h3>原始提示词</h3><p class="prompt">{esc(s["prompt"] or "未提供")}</p>']
    overall = record["overall"]
    title = "综合评分" if overall["status"] == "complete" else "综合暂定分"
    score_text = f'{overall["score"]:.1f} / 100' if overall["score"] is not None else "暂不可评分"
    text.insert(1, f'<h3>{title}：{score_text}</h3><p>{esc(overall["description"])} · 已覆盖 {overall["coverage"]}% · {overall["version"]}</p>')
    if overall["missing"]:
        text.append('<p>缺少：' + esc('、'.join(overall["missing"])) + '；暂定分按已完成项目的权重换算。</p>')
    if overall["reason"]:
        text.append('<p>' + esc(overall["reason"]) + '</p>')
    text.append('<details><summary>综合评分构成</summary><table><tr><th>项目</th><th>标准权重</th><th>分项 / 100</th><th>计入分数</th></tr>')
    for c in overall["components"]:
        value = f'{c["score"]:.2f}' if c["score"] is not None else esc(c["reason"] or "未计算")
        text.append(f'<tr><td>{c["label"]}</td><td>{c["weight"]:.0%}</td><td>{value}</td><td>{c["contribution"]:.2f}</td></tr>')
    text.append('</table></details>')
    clap = results.get("clap", {})
    scoring_text = (clap.get("result") or {}).get("value") or {}
    english = scoring_text.get("text_used") or s.get("prompt_en")
    if english:
        text.append(f'<h3>英文评分文本</h3><p class="prompt">{esc(english)}</p>')
    if record.get("job"):
        text.append(f'<p>评估任务：{esc(record["job"]["id"])}（使用该任务的输入快照）</p>')
    text.append('<table><tr><th>指标</th><th>结果</th></tr>')
    for name, value in record["metrics"].items():
        label = METRIC_LABELS["clap_score" if name == "clap" else name]
        display = f'{value * 100:.2f}%' if name.endswith("ratio") else f'{value:.4f}'
        text.append(f'<tr><td>{esc(label)}</td><td>{display}</td></tr>')
    text.append('</table><h3>评估状态</h3><table><tr><th>评估器</th><th>状态 / 原因</th></tr>')
    states = {"success": "成功", "failed": "失败", "skipped": "未计算", "cancelled": "已取消", "queued": "排队中", "running": "运行中"}
    for metric in ("basic", "clap", "songeval", "translation"):
        it = results.get(metric)
        if not it and metric == "translation":
            continue
        status = ("需要重算" if it.get("stale") else states[it["status"]]) if it else ("本任务未选择" if record.get("job") else "尚未评估")
        reason = esc((it or {}).get("reason") or "")
        text.append(f'<tr><td>{METRIC_LABELS[metric]}</td><td>{status} {reason}</td></tr>')
    text.append('</table></section>')
    return ''.join(text)


def export_sample_html(record):
    payload = html.escape(json.dumps(record, ensure_ascii=False, indent=2))
    return ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>单曲评估报告</title>'
            '<style>body{font:16px/1.7 system-ui;max-width:1000px;margin:40px auto;padding:20px;color:#243d34}'
            'table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #ddd}'
            '.prompt,pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#276b58}</style>'
            '<h1>单曲评估报告</h1>' + song_html(record) + '<details><summary>完整结果与溯源</summary><pre>' + payload + '</pre></details></html>')


def report(samples):
    records, groups = [], defaultdict(list)
    for s in samples:
        if s["role"] != "generated":
            continue
        results = latest_results(s)
        record = scored_record(s, results)
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
            "notes": ["CLAP 报告音频与评分文本的余弦相似度。", "FAD 仅比较集合；不同协议分数不能混比。",
                      "综合分采用 overall-v1 自定义权重；仅完整评分参与模型综合分统计。"]}


def export_csv(data):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["sample_id", "filename", "model_id", "model_version", "prompt_id", "metric", "status", "value", "reason", "sha256"])
    for r in data["records"]:
        s = r["sample"]
        for metric, it in r["results"].items():
            writer.writerow([s["id"], s["filename"], s["model_id"], s["model_version"], s["prompt_id"], metric,
                             "stale" if it["stale"] else it["status"], json.dumps(it["result"], ensure_ascii=False), it["reason"], s["sha256"]])
        overall = r["overall"]
        writer.writerow([s["id"], s["filename"], s["model_id"], s["model_version"], s["prompt_id"], "overall_score",
                         overall["status"], json.dumps(overall, ensure_ascii=False), overall["reason"], s["sha256"]])
    for it in data["fad"]:
        writer.writerow(["", "", *it["snapshot"]["group"][:2], "", "fad", it["status"], json.dumps(it["result"], ensure_ascii=False), it["reason"], ""])
    return "\ufeff" + output.getvalue()


def export_html(data):
    escape = html.escape
    body = []
    if data["records"]:
        body.append('<h2>单曲评估结果</h2>')
        body.extend(song_html(r) for r in data["records"])
        body.append('<h2>模型汇总</h2>')
    for g in data["groups"]:
        body.append(f"<h2>{escape(' / '.join(g['group']))}</h2><p>{g['count']} 首 · {g['prompt_count']} 个提示词</p><table><tr><th>指标</th><th>提示词等权均值</th><th>P10–P90</th></tr>")
        for k, v in g["metrics"].items():
            body.append(f"<tr><td>{escape(METRIC_LABELS.get(k, k))}</td><td>{v['mean']:.4f}</td><td>{v['p10']:.4f} – {v['p90']:.4f}</td></tr>")
        body.append("</table>")
    detail = escape(json.dumps(data, indent=2, ensure_ascii=False))
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>音乐评估报告</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px;color:#182526}table{border-collapse:collapse;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1{color:#176b58}</style><h1>CPU 音乐评估报告</h1><p>' + escape(' '.join(data["notes"])) + '</p>' + ''.join(body) + '<details><summary>完整结果、配对统计、协议与输入哈希</summary><pre>' + detail + '</pre></details></html>'
