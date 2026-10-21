import csv
import hashlib
import io
import json
import random
import re
import subprocess
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db
from .audio import ffmpeg, waveform
from .config import DATA, ROOT, MODELS, PROTOCOL, settings
from .jobs import create_job, job_view, runner
from .reports import latest_results, report, export_csv, export_html


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    runner.start()
    yield
    runner.close()


app = FastAPI(title="CPU 音乐评估平台", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def local_access(request: Request, call_next):
    # Local application: prevent browser cross-origin writes / DNS rebinding.
    host = request.headers.get("host", "").split(":")[0]
    if host not in ("127.0.0.1", "localhost", "testserver"):
        return Response("仅允许本机访问", status_code=403)
    origin = request.headers.get("origin")
    if origin and origin not in ("http://" + request.headers.get("host", ""), "http://localhost:5173", "http://127.0.0.1:5173"):
        return Response("跨域请求被拒绝", status_code=403)
    return await call_next(request)


def sample_or_404(sid):
    s = db.one("SELECT * FROM samples WHERE id=?", (sid,))
    if not s:
        raise HTTPException(404, "样本不存在")
    return s


def selected(ids="", model="", audio_type="", tag="", version=""):
    samples = db.rows("SELECT * FROM samples ORDER BY created DESC")
    wanted = set(ids.split(",")) if ids else None
    return [s for s in samples if (wanted is None or s["id"] in wanted)
            and (not model or model == s["model_id"])
            and (not audio_type or audio_type == s["audio_type"])
            and (not version or version == s["model_version"])
            and (not tag or tag in [t.strip() for t in s["tags"].split(",")])]


class Metadata(BaseModel):
    prompt_id: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default="", max_length=20000)
    prompt_en: str = Field(default="", max_length=20000)
    model_id: str = Field(min_length=1, max_length=200)
    model_version: str = Field(default="", max_length=200)
    audio_type: Literal["song", "instrumental"] = "song"
    seed: str = Field(default="", max_length=100)
    tags: str = Field(default="", max_length=1000)
    role: Literal["generated", "reference"] = "generated"


class JobRequest(BaseModel):
    sample_ids: list[str] = Field(min_length=1)
    metrics: list[Literal["basic", "clap", "songeval", "fad", "translation"]] = Field(min_length=1)
    reference_ids: list[str] = []
    exploratory: bool = False


class SettingsRequest(BaseModel):
    offline: bool = False
    threads: int = Field(default=6, ge=1, le=32)
    timeout_seconds: int = Field(default=1800, ge=10, le=86400)
    memory_limit_gb: float = Field(default=22, ge=.1, le=128)
    model_cache: str
    songeval_python: str
    songeval_dir: str


@app.get("/api/health")
def health():
    return {"ok": True, "protocol": PROTOCOL}


@app.get("/api/settings")
def get_settings():
    import importlib.util
    return {"settings": settings(), "models": MODELS, "model_dependencies": bool(importlib.util.find_spec("torch")),
            "songeval_installed": Path(settings()["songeval_python"]).exists(),
            "fad_installed": (ROOT / ".venv-fad/Scripts/python.exe").exists()}


@app.put("/api/settings")
def update_settings(body: SettingsRequest):
    p = DATA / "settings.json"
    temp = p.with_suffix(".tmp")
    temp.write_text(json.dumps(body.model_dump(), ensure_ascii=False), encoding="utf-8")
    temp.replace(p)
    return get_settings()


@app.get("/api/samples")
def samples(ids: str = "", model: str = "", audio_type: str = "", tag: str = ""):
    return [{**{k: v for k, v in s.items() if k != "path"}, "results": latest_results(s)} for s in selected(ids, model, audio_type, tag)]


@app.post("/api/import")
async def upload(files: list[UploadFile] = File(...), metadata: str = Form("{}"), manifest: UploadFile | None = File(None)):
    try:
        defaults = json.loads(metadata)
        mappings = []
        if manifest:
            raw = (await manifest.read(8 * 1024 * 1024 + 1))
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("清单不能超过 8MB")
            text = raw.decode("utf-8-sig")
            mappings = list(csv.DictReader(io.StringIO(text))) if (manifest.filename or "").endswith(".csv") else [json.loads(line) for line in text.splitlines() if line.strip()]
        names = [f.filename for f in files]
        if len(names) != len(set(names)):
            raise ValueError("同一次导入中有重名文件，请先重命名以便准确关联清单")
        mapping = {}
        for row in mappings:
            key = row.get("audio") or row.get("filename")
            if not key or key not in names or key in mapping:
                raise ValueError("清单 audio 必须唯一且与上传文件名完全一致")
            mapping[key] = row
        if manifest and set(mapping) != set(names):
            raise ValueError("清单与上传文件必须一一对应")
        prepared = []
        for f in files:
            if Path(f.filename or "").suffix.lower() not in (".wav", ".flac", ".mp3"):
                raise ValueError("只支持 WAV、FLAC、MP3")
            attrs = Metadata.model_validate({**defaults, **mapping.get(f.filename, {})}).model_dump()
            prepared.append((f, attrs))
    except (ValueError, TypeError) as e:
        raise HTTPException(422, str(e))
    created, paths = [], []
    try:
        for f, attrs in prepared:
            sid = db.uid()
            path = DATA / "audio" / (sid + Path(f.filename).suffix.lower())
            paths.append(path)
            sha = hashlib.sha256()
            size = 0
            with path.open("wb") as out:
                while chunk := await f.read(1024 * 1024):
                    size += len(chunk)
                    if size > 512 * 1024 * 1024:
                        raise ValueError("单个音频不能超过 512MB")
                    sha.update(chunk)
                    out.write(chunk)
            if not size:
                raise ValueError("不能导入空文件")
            created.append({**attrs, "id": sid, "filename": Path(f.filename).name, "path": str(path), "sha256": sha.hexdigest(),
                            "translation_source": "manual" if attrs["prompt_en"] else ""})
        # Publish only after the complete batch has been staged.
        with db.connect() as c:
            for row in created:
                row["created"] = time.time()
                c.execute(f"INSERT INTO samples ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", list(row.values()))
    except Exception as e:
        for path in paths:
            path.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    return {"sample_ids": [s["id"] for s in created]}


@app.patch("/api/samples/{sid}")
def edit_sample(sid: str, body: Metadata):
    previous = sample_or_404(sid)
    row = body.model_dump()
    source = previous["translation_source"]
    if row["prompt"] != previous["prompt"] and row["prompt_en"] == previous["prompt_en"]:
        row["prompt_en"] = ""
        source = ""
    elif row["prompt_en"] != previous["prompt_en"]:
        source = "manual"
    row["translation_source"] = source
    db.execute(f"UPDATE samples SET {','.join(k+'=?' for k in row)} WHERE id=?", [*row.values(), sid])
    return {"ok": True}


@app.get("/api/samples/{sid}/waveform")
def audio_waveform(sid: str):
    try:
        return waveform(sample_or_404(sid)["path"])
    except Exception as e:
        raise HTTPException(422, str(e))


def media_response(s, normalized=False):
    path = Path(s["path"])
    if normalized:
        dest = DATA / "cache" / ("listen-" + s["sha256"] + "-lufs18-v1.wav")
        if not dest.exists():
            # Playback derivative only. Evaluation always reads the original.
            tmp = dest.with_suffix(".tmp.wav")
            p = subprocess.run([ffmpeg(), "-v", "error", "-y", "-i", str(path), "-af",
                                "loudnorm=I=-18:TP=-1.5:LRA=11", "-ar", "48000", str(tmp)], capture_output=True, timeout=180)
            if p.returncode:
                raise HTTPException(422, "试听响度对齐失败")
            tmp.replace(dest)
        path = dest
    return FileResponse(path, headers={"Content-Disposition": "inline", "Cache-Control": "private, max-age=3600"})


@app.get("/api/samples/{sid}/audio")
def audio(sid: str, normalized: bool = False):
    return media_response(sample_or_404(sid), normalized)


@app.post("/api/jobs")
def new_job(body: JobRequest):
    try:
        jid = create_job(body.sample_ids, list(dict.fromkeys(body.metrics)), body.reference_ids, body.exploratory)
        return job_view(jid)
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/jobs")
def jobs():
    return [job_view(j["id"]) for j in db.rows("SELECT id FROM jobs ORDER BY created DESC LIMIT 30")]


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = job_view(jid)
    if not job:
        raise HTTPException(404, "任务不存在")
    return job


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    get_job(jid)
    db.execute("UPDATE jobs SET cancel=1 WHERE id=?", (jid,))
    return {"ok": True}


@app.post("/api/jobs/{jid}/retry")
def retry_job(jid: str):
    job = get_job(jid)
    if job["status"] in ("running", "queued"):
        raise HTTPException(409, "请等待任务结束或取消后重试")
    db.execute("UPDATE items SET status='queued',reason=NULL,result=NULL WHERE job_id=? AND status IN ('failed','skipped','cancelled')", (jid,))
    config = job["config"]
    config["options"].update(settings())
    db.execute("UPDATE jobs SET cancel=0,status='queued',updated=?,config=? WHERE id=?", (time.time(), json.dumps(config), jid))
    return get_job(jid)


@app.get("/api/report")
def get_report(ids: str = "", model: str = "", audio_type: str = "", tag: str = "", version: str = ""):
    return report(selected(ids, model, audio_type, tag, version))


@app.get("/api/export/{kind}")
def export(kind: Literal["json", "csv", "html", "bundle"], ids: str = "", model: str = "", audio_type: str = "", tag: str = "", version: str = ""):
    ss = selected(ids, model, audio_type, tag, version)
    data = report(ss)
    if kind == "bundle":
        path = DATA / "exports" / (db.uid() + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("report.json", json.dumps(data, ensure_ascii=False, indent=2))
            z.writestr("report.html", export_html(data))
            for s in ss:
                z.write(s["path"], "audio/" + s["id"] + Path(s["path"]).suffix)
        return FileResponse(path, filename="music-eval-with-audio.zip")
    content = {"json": lambda: json.dumps(data, ensure_ascii=False, indent=2), "csv": lambda: export_csv(data), "html": lambda: export_html(data)}[kind]()
    return Response(content, media_type={"json": "application/json", "csv": "text/csv", "html": "text/html"}[kind],
                    headers={"Content-Disposition": f'attachment; filename="music-eval.{kind}"'})


class BlindRequest(BaseModel):
    sample_ids: list[str] = Field(min_length=2, max_length=2)


class VoteRequest(BaseModel):
    choice: Literal["a", "b", "tie", "skip"]
    note: str = Field(default="", max_length=2000)


@app.post("/api/blind")
def blind(body: BlindRequest):
    a, b = [sample_or_404(sid) for sid in body.sample_ids]
    if a["id"] == b["id"] or a["prompt_id"] != b["prompt_id"] or a["audio_type"] != b["audio_type"]:
        raise HTTPException(422, "盲听需要同一提示词、同类的两首不同作品")
    pair = random.sample([a["id"], b["id"]], 2)
    sid = db.uid()
    db.execute("INSERT INTO sessions(id,a,b,created) VALUES(?,?,?,?)", (sid, *pair, time.time()))
    return {"id": sid, "prompt": a["prompt"], "audio_a": f"/api/blind/{sid}/audio/a", "audio_b": f"/api/blind/{sid}/audio/b"}


@app.get("/api/blind/{sid}/audio/{side}")
def blind_audio(sid: str, side: Literal["a", "b"], normalized: bool = False):
    row = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not row:
        raise HTTPException(404, "盲听不存在")
    return media_response(sample_or_404(row[side]), normalized)


@app.post("/api/blind/{sid}/vote")
def vote(sid: str, body: VoteRequest):
    row = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not row:
        raise HTTPException(404, "盲听不存在")
    if row["revealed"]:
        raise HTTPException(409, "该轮已揭晓，不能修改投票")
    db.execute("UPDATE sessions SET choice=?,note=? WHERE id=? AND revealed=0", (body.choice, body.note, sid))
    return {"ok": True}


@app.post("/api/blind/{sid}/reveal")
def reveal(sid: str):
    row = db.one("SELECT * FROM sessions WHERE id=?", (sid,))
    if not row or not row["choice"]:
        raise HTTPException(409, "请先投票再揭晓")
    db.execute("UPDATE sessions SET revealed=1 WHERE id=?", (sid,))
    return {"a": {k: sample_or_404(row["a"])[k] for k in ("model_id", "model_version", "filename")},
            "b": {k: sample_or_404(row["b"])[k] for k in ("model_id", "model_version", "filename")}, "choice": row["choice"]}


@app.get("/api/votes")
def vote_stats():
    result = {}
    for row in db.rows("SELECT * FROM sessions WHERE revealed=1"):
        for side in ("a", "b"):
            s = sample_or_404(row[side])
            key = s["model_id"] + " / " + s["model_version"]
            stats = result.setdefault(key, {"wins": 0, "losses": 0, "ties": 0, "skips": 0})
            choice = row["choice"]
            stats["ties" if choice == "tie" else "skips" if choice == "skip" else "wins" if choice == side else "losses"] += 1
    for stats in result.values():
        n = stats["wins"] + stats["losses"]
        stats["win_rate"] = stats["wins"] / n if n else None
    return result


@app.get("/api/template/{kind}")
def template(kind: Literal["csv", "jsonl"]):
    row = {"audio": "example.wav", "prompt_id": "p001", "prompt": "舒缓的钢琴独奏", "prompt_en": "A calm solo piano piece",
           "model_id": "model-a", "model_version": "v1", "audio_type": "instrumental", "seed": "42", "tags": "piano,calm", "role": "generated"}
    if kind == "jsonl":
        content = json.dumps(row, ensure_ascii=False) + "\n"
    else:
        out = io.StringIO(newline="")
        writer = csv.DictWriter(out, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)
        content = "\ufeff" + out.getvalue()
    return Response(content, media_type="text/plain", headers={"Content-Disposition": f'attachment; filename="manifest.{kind}"'})


@app.post("/api/demo")
def demo():
    existing = db.rows("SELECT id FROM samples WHERE tags='demo,synthetic'")
    if existing:
        return {"sample_ids": [r["id"] for r in existing]}
    created = []
    sr = 24000
    for pid, notes in (("demo-calm", [261.63, 329.63, 392]), ("demo-bright", [293.66, 369.99, 440])):
        for model in ("示例 A", "示例 B"):
            t = np.arange(sr * 12) / sr
            x = sum(np.sin(2 * np.pi * f * t) for f in notes) * .06
            x *= np.minimum(t, 1) * np.minimum(12 - t, 1)
            if model == "示例 B":
                x[int(sr * 4):int(sr * 5)] = 0
            path = DATA / "audio" / (db.uid() + ".wav")
            sf.write(path, x, sr)
            s = db.insert_sample({"filename": f"{pid}-{model}.wav", "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "prompt_id": pid, "prompt": "合成和弦示例，仅用于检查流程，不代表真实 AI 音乐质量", "prompt_en": "A synthetic sustained chord",
                                  "translation_source": "manual", "model_id": model, "model_version": "demo", "audio_type": "instrumental", "tags": "demo,synthetic"})
            created.append(s["id"])
    return {"sample_ids": created}


dist = ROOT / "frontend/dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
