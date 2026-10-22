"""Versioned application scoring policy; evaluated model outputs stay unchanged."""
import math

VERSION = "overall-v1"
WEIGHTS = {"aesthetics": .7, "adherence": .2, "health": .1}
DIMENSIONS = ("Coherence", "Musicality", "Memorability", "Clarity", "Naturalness")


def overall_score(results, audio_type):
    components = []

    def component(key, label, metric, calculate):
        item = results.get(metric)
        reason = None
        value = None
        if not item:
            reason = "尚未评估"
        elif item.get("stale"):
            reason = "输入已变更，需要重新评估"
        elif item["status"] != "success":
            reason = item.get("reason") or "指标尚未成功完成"
        else:
            try:
                value = calculate(item["result"]["value"])
                if not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError("分项分数越界")
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                value, reason = None, "评分数据缺失或无效"
        components.append({"id": key, "label": label, "weight": WEIGHTS[key], "score": value,
                           "reason": reason, "effective_weight": 0, "contribution": 0})

    def aesthetics(v):
        names = DIMENSIONS[:4] if audio_type == "instrumental" else DIMENSIONS
        scores = [float(v["scores"][name]) for name in names]
        if any(not math.isfinite(x) or not 1 <= x <= 5 for x in scores):
            raise ValueError("美学分数越界")
        return sum(scores) / len(scores) / 5 * 100

    def adherence(v):
        value = float(v["score"])
        if not math.isfinite(value) or not -1 <= value <= 1:
            raise ValueError("CLAP 分数越界")
        return max(0, value) * 100

    def health(v):
        silence, near = float(v["silence_ratio"]), float(v["near_full_scale_ratio"])
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in (silence, near)):
            raise ValueError("音频比例越界")
        if v.get("invalid_values", 0) or silence == 1:
            return 0
        return 100 - 50 * min(1, near / .01) - 50 * min(1, max(0, silence - .1) / .5)

    component("aesthetics", "音乐美学", "songeval", aesthetics)
    component("adherence", "提示词匹配", "clap", adherence)
    component("health", "音频健康", "basic", health)
    coverage = sum(c["weight"] for c in components if c["score"] is not None)
    invalid = None
    basic = results.get("basic")
    if basic and basic["status"] == "success" and not basic.get("stale"):
        value = basic["result"]["value"]
        if value.get("invalid_values", 0):
            invalid = "音频包含 NaN/Inf，请修复后重新评估"
        elif value.get("silence_ratio") == 1:
            invalid = "全部音频窗口低于静音阈值，无法给出综合评分"
    score = None
    if coverage and not invalid:
        for c in components:
            if c["score"] is not None:
                c["effective_weight"] = c["weight"] / coverage
                c["contribution"] = c["score"] * c["effective_weight"]
        score = round(sum(c["contribution"] for c in components), 1)
    status = "invalid" if invalid else "complete" if math.isclose(coverage, 1) else "partial" if coverage else "unavailable"
    return {"version": VERSION, "max_score": 100, "score": score, "status": status,
            "coverage": round(coverage * 100), "components": components, "reason": invalid,
            "missing": [c["label"] for c in components if c["score"] is None],
            "exploratory": audio_type == "instrumental",
            "description": "项目自定义加权评分：音乐美学70%、提示词匹配20%、音频健康10%"}
