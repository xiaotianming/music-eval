import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
import psutil
from . import db
from .config import DATA, ROOT, MODELS, PROTOCOL, settings
from .metrics import fingerprint

TERMINAL = ("success", "failed", "skipped", "cancelled")


def signature(sample, metric):
    value = {"sha256": sample["sha256"], "metric": metric, "protocol": PROTOCOL}
    if metric in ("clap", "translation"):
        value.update(prompt=sample["prompt"], translation_model=MODELS["translation"])
    if metric == "clap":
        value.update(prompt_en=sample["prompt_en"], model=MODELS["clap"])
    if metric == "songeval":
        value.update(audio_type=sample["audio_type"], model=MODELS["songeval"], muq=MODELS["muq"])
    if metric == "fad":
        value.update(model=MODELS["fadtk"], checkpoint=MODELS["fad_clap"], text_architecture=MODELS["roberta"])
    return value


def create_job(sample_ids, metrics, reference_ids=None, exploratory=False):
    samples = [db.one("SELECT * FROM samples WHERE id=?", (s,)) for s in dict.fromkeys(sample_ids)]
    if not samples or any(s is None for s in samples):
        raise ValueError("请选择存在的音频样本")
    references = [db.one("SELECT * FROM samples WHERE id=?", (s,)) for s in dict.fromkeys(reference_ids or [])]
    if any(s is None or s["role"] != "reference" for s in references):
        raise ValueError("参考音频不存在或未标记为参考集")
    if any(s["role"] != "generated" for s in samples) and "fad" in metrics:
        raise ValueError("FAD 生成集不能包含参考音频")
    if {s["sha256"] for s in samples} & {s["sha256"] for s in references}:
        raise ValueError("生成集和参考集包含相同音频，请检查参考集污染")
    job_id = db.uid()
    options = settings()
    options["fad_python"] = str(ROOT / ".venv-fad" / "Scripts" / "python.exe")
    config = {"metrics": metrics, "exploratory": exploratory, "references": references,
              "options": options, "protocol": PROTOCOL, "models": MODELS,
              "hardware": {"platform": platform.platform(), "processor": platform.processor(),
                           "logical_cpus": os.cpu_count(), "memory_gb": psutil.virtual_memory().total / 2**30}}
    with db.connect() as c:
        now = time.time()
        c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,0)", (job_id, "queued", json.dumps(config), now, now))
        work = [(s, m, {}) for m in metrics if m != "fad" for s in samples]
        if "fad" in metrics:
            groups = {}
            for s in samples:
                groups.setdefault((s["model_id"], s["model_version"], s["audio_type"]), []).append(s)
            for group, ss in groups.items():
                refs = [r for r in references if r["audio_type"] == group[2]]
                work.append((ss[0], "fad", {"samples": ss, "references": refs, "group": group}))
        for s, metric, extra in work:
            snapshot = {"sample": s, **extra, "signature": signature(s, metric)}
            key = fingerprint({"signature": snapshot["signature"], "extra": extra,
                               "exploratory": exploratory if metric == "songeval" else None})
            c.execute("INSERT INTO items(id,job_id,sample_id,metric,status,cache_key,snapshot) VALUES(?,?,?,?,?,?,?)",
                      (db.uid(), job_id, s["id"], metric, "queued", key, json.dumps(snapshot)))
    return job_id


def job_view(job_id):
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if job:
        job["config"] = json.loads(job["config"])
        job["items"] = [db.decode_item(i) for i in db.rows("SELECT * FROM items WHERE job_id=? ORDER BY rowid", (job_id,))]
        job["done"] = sum(i["status"] in TERMINAL for i in job["items"])
        job["total"] = len(job["items"])
    return job


def stop_tree(p):
    try:
        proc = psutil.Process(p.pid)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        proc.kill()
    except psutil.NoSuchProcess:
        pass
    p.wait(timeout=10)


class Runner:
    def __init__(self):
        self.stop = threading.Event()
        self.thread = None
        self.lock_file = None

    def start(self):
        if self.thread and self.thread.is_alive():
            raise RuntimeError("评估执行器已经运行")
        handle = (DATA / "runner.lock").open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            handle.close()
            raise RuntimeError("该数据目录已有评估服务运行，请使用现有服务或更换 MUSIC_EVAL_DATA") from e
        self.lock_file = handle
        db.execute("UPDATE items SET status='queued' WHERE status='running'")
        db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        self.stop.clear()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=15)
        if self.lock_file:
            self.lock_file.close()
            self.lock_file = None

    def loop(self):
        while not self.stop.is_set():
            job = db.one("SELECT * FROM jobs WHERE status IN ('queued','running') ORDER BY created LIMIT 1")
            if not job:
                self.stop.wait(.4)
                continue
            try:
                self.run_job(job)
            except Exception as e:
                db.execute("UPDATE items SET status='failed', reason=? WHERE job_id=? AND status IN ('queued','running')",
                           (f"任务调度错误：{e}", job["id"]))
                db.execute("UPDATE jobs SET status='failed',updated=? WHERE id=?", (time.time(), job["id"]))

    def run_job(self, job):
        jid = job["id"]
        config = json.loads(job["config"])
        db.execute("UPDATE jobs SET status='running',updated=? WHERE id=?", (time.time(), jid))
        for item in db.rows("SELECT * FROM items WHERE job_id=? AND status='queued' ORDER BY rowid", (jid,)):
            if self.stop.is_set():
                return
            if db.one("SELECT cancel FROM jobs WHERE id=?", (jid,))["cancel"]:
                break
            self.run_item(item, config)
            db.execute("UPDATE jobs SET updated=? WHERE id=?", (time.time(), jid))
        if self.stop.is_set():
            return
        cancelled = db.one("SELECT cancel FROM jobs WHERE id=?", (jid,))["cancel"]
        if cancelled:
            db.execute("UPDATE items SET status='cancelled',reason='用户取消' WHERE job_id=? AND status='queued'", (jid,))
        failed = db.one("SELECT count(*) AS n FROM items WHERE job_id=? AND status='failed'", (jid,))["n"]
        status = "cancelled" if cancelled else ("completed_with_errors" if failed else "completed")
        db.execute("UPDATE jobs SET status=?,updated=? WHERE id=?", (status, time.time(), jid))

    def run_item(self, item, config):
        snapshot = json.loads(item["snapshot"])
        if item["metric"] == "fad" and not snapshot.get("references"):
            db.execute("UPDATE items SET status='skipped',reason='缺少参考集；FAD 只能比较音频集合' WHERE id=?", (item["id"],))
            return
        cached = db.one("SELECT result FROM cache WHERE key=?", (item["cache_key"],))
        if cached:
            result = json.loads(cached["result"])
            result["cache_hit"] = True
            db.execute("UPDATE items SET status='success',result=?,elapsed=0,peak_mb=0 WHERE id=?",
                       (json.dumps(result), item["id"]))
            self.apply_translation(item, snapshot, result)
            return
        options = config["options"]
        interpreter = sys.executable
        if item["metric"] in ("songeval", "fad"):
            interpreter = options["songeval_python"] if item["metric"] == "songeval" else options["fad_python"]
            if not Path(interpreter).exists():
                db.execute("UPDATE items SET status='skipped',reason=? WHERE id=?",
                           (f"{item['metric']} 独立环境未安装，请运行对应 setup 脚本", item["id"]))
                return
        payload = {"sample": snapshot["sample"], "metric": item["metric"], "options": options,
                   "models": config["models"],
                   "exploratory": config["exploratory"], "samples": snapshot.get("samples", []),
                   "references": snapshot.get("references", [])}
        db.execute("UPDATE items SET status='running' WHERE id=?", (item["id"],))
        task_dir = DATA / "tasks" / item["id"]
        task_dir.mkdir(exist_ok=True)
        start = time.perf_counter()
        peak = 0
        aborted = None
        env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "CUDA_VISIBLE_DEVICES": ""}
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (task_dir / "result.json").open("w", encoding="utf-8") as out, (task_dir / "worker.log").open("w", encoding="utf-8") as log:
            p = subprocess.Popen([interpreter, "-m", "backend.worker"], cwd=ROOT, stdin=subprocess.PIPE,
                                 stdout=out, stderr=log, text=True, encoding="utf-8", env=env, creationflags=flags)
            p.stdin.write(json.dumps(payload))
            p.stdin.close()
            while p.poll() is None:
                try:
                    proc = psutil.Process(p.pid)
                    memory = sum(q.memory_info().rss for q in [proc, *proc.children(recursive=True)] if q.is_running())
                    peak = max(peak, memory / 2**20)
                except psutil.Error:
                    pass
                if self.stop.is_set():
                    stop_tree(p)
                    db.execute("UPDATE items SET status='queued' WHERE id=?", (item["id"],))
                    return
                if db.one("SELECT cancel FROM jobs WHERE id=?", (item["job_id"],))["cancel"]:
                    aborted = ("cancelled", "用户取消")
                elif time.perf_counter() - start > options["timeout_seconds"]:
                    aborted = ("failed", "超过单项时间限制；未截短音频，可调整设置后重试")
                elif peak > options["memory_limit_gb"] * 1024:
                    aborted = ("failed", "超过内存限制；未截短音频，其他指标继续")
                if aborted:
                    stop_tree(p)
                    break
                self.stop.wait(.15)
        elapsed = time.perf_counter() - start
        if aborted:
            status, reason = aborted
            envelope = {"status": status, "reason": reason}
        else:
            try:
                envelope = json.loads((task_dir / "result.json").read_text(encoding="utf-8"))
            except (ValueError, OSError):
                envelope = {"status": "failed", "reason": "子进程异常退出，请查看 data/tasks/" + item["id"] + "/worker.log"}
        result = {"value": envelope.get("value"), "protocol": PROTOCOL, "models": config["models"],
                  "cache_hit": False, "elapsed": elapsed, "peak_mb": peak, "hardware": config["hardware"]}
        db.execute("UPDATE items SET status=?,reason=?,result=?,elapsed=?,peak_mb=? WHERE id=?",
                   (envelope["status"], envelope.get("reason"), json.dumps(result), elapsed, peak, item["id"]))
        if envelope["status"] == "success":
            db.execute("INSERT OR REPLACE INTO cache VALUES(?,?)", (item["cache_key"], json.dumps(result)))
            self.apply_translation(item, snapshot, result)

    @staticmethod
    def apply_translation(item, snapshot, result):
        if item["metric"] == "translation":
            s = snapshot["sample"]
            db.execute("UPDATE samples SET prompt_en=?,translation_source=? WHERE id=? AND prompt=? AND prompt_en=?",
                       (result["value"]["text"], result["value"]["source"], s["id"], s["prompt"], s["prompt_en"]))


runner = Runner()
