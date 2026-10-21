import io
import json
import time
import zipfile
import numpy as np
import soundfile as sf
import pytest
from backend import db
from backend.config import PROTOCOL
from backend.jobs import signature, create_job, Runner, job_view
from backend.metrics import fingerprint, token_chunks
from backend.reports import report


def wav(seconds=.6):
    out = io.BytesIO()
    sf.write(out, np.sin(np.arange(int(8000 * seconds)) * .2) * .1, 8000, format="WAV")
    return out.getvalue()


def upload(client, model="A", pid="p1", **kw):
    metadata = {"model_id": model, "prompt_id": pid, "prompt": "A calm piano piece", "audio_type": "song", **kw}
    r = client.post("/api/import", files={"files": ("中文 曲.wav", wav())}, data={"metadata": json.dumps(metadata)})
    assert r.status_code == 200, r.text
    return r.json()["sample_ids"][0]


def wait_job(client, jid):
    until = time.time() + 40
    while time.time() < until:
        value = client.get("/api/jobs/" + jid).json()
        if value["status"] not in ("running", "queued"):
            return value
        time.sleep(.15)
    pytest.fail("job timeout")


def test_upload_evaluate_cache_invalidation_export(client):
    sid = upload(client)
    r = client.post("/api/jobs", json={"sample_ids": [sid], "metrics": ["basic"]})
    job = wait_job(client, r.json()["id"])
    assert job["items"][0]["status"] == "success", job
    assert job["items"][0]["result"]["value"]["duration"] == .6
    r = client.post("/api/jobs", json={"sample_ids": [sid], "metrics": ["basic"]})
    assert wait_job(client, r.json()["id"])["items"][0]["result"]["cache_hit"]
    s = db.one("SELECT * FROM samples WHERE id=?", (sid,))
    old = {m: fingerprint(signature(s, m)) for m in ("basic", "clap", "songeval", "translation")}
    client.patch("/api/samples/" + sid, json={**s, "prompt_en": "Edited English prompt"})
    s = db.one("SELECT * FROM samples WHERE id=?", (sid,))
    new = {m: fingerprint(signature(s, m)) for m in old}
    assert new["clap"] != old["clap"]
    assert all(new[m] == old[m] for m in ("basic", "songeval", "translation"))
    assert client.get(f"/api/samples/{sid}/waveform").status_code == 200
    assert client.get(f"/api/samples/{sid}/audio", headers={"Range": "bytes=0-100"}).status_code == 206
    for kind in ("html", "json", "csv"):
        r = client.get("/api/export/" + kind)
        assert r.status_code == 200
        assert "attachment" in r.headers["content-disposition"]
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/export/bundle").content))
    assert "report.html" in z.namelist()
    assert any(name.startswith("audio/") for name in z.namelist())


def test_manifest_atomic_and_duplicate_names(client):
    manifest = json.dumps({"audio": "a.wav", "model_id": "A", "prompt_id": "p", "audio_type": "instrumental"})
    r = client.post("/api/import", files=[("files", ("a.wav", wav())), ("manifest", ("manifest.jsonl", manifest.encode()))])
    assert r.status_code == 200, r.text
    before = len(client.get("/api/samples").json())
    r = client.post("/api/import", files=[("files", ("a.wav", wav())), ("files", ("a.wav", wav()))], data={"metadata": '{"model_id":"B","prompt_id":"p"}'})
    assert r.status_code == 422
    assert len(client.get("/api/samples").json()) == before
    r = client.post("/api/import", files=[("files", ("a.wav", wav())), ("files", ("bad.txt", b"bad"))], data={"metadata": '{"model_id":"B","prompt_id":"p"}'})
    assert r.status_code == 422
    assert len(client.get("/api/samples").json()) == before


def test_blind_and_reference_contamination(client):
    a, b = upload(client), upload(client, "B")
    session = client.post("/api/blind", json={"sample_ids": [a, b]}).json()
    assert not any(k in session for k in ("a", "b", "sample_ids", "filename"))
    sid = session["id"]
    assert client.post(f"/api/blind/{sid}/reveal").status_code == 409
    assert client.get(session["audio_a"]).status_code == 200
    assert client.post(f"/api/blind/{sid}/vote", json={"choice": "tie", "note": "same"}).status_code == 200
    revealed = client.post(f"/api/blind/{sid}/reveal").json()
    assert {revealed["a"]["model_id"], revealed["b"]["model_id"]} == {"A", "B"}
    assert client.post(f"/api/blind/{sid}/vote", json={"choice": "a"}).status_code == 409
    assert all(v["ties"] == 1 and v["win_rate"] is None for v in client.get("/api/votes").json().values())
    ref = upload(client, "real", role="reference")
    assert client.post('/api/jobs', json={"sample_ids":[a,b],"reference_ids":[ref],"metrics":["fad"]}).status_code == 422


def test_fad_missing_reference_is_explicit(client):
    a, b = upload(client), upload(client, "B")
    jid = client.post('/api/jobs', json={"sample_ids":[a,b],"metrics":["fad"]}).json()["id"]
    job = wait_job(client, jid)
    assert all(it["status"] == "skipped" for it in job["items"])
    assert all(it["reason"] for it in job["items"])


def test_cancel_recovery_and_retry():
    # Recovery uses the original frozen snapshot, including for renamed samples.
    sample = db.insert_sample({"filename":"x.wav","path":"missing.wav","sha256":"x","prompt_id":"p","model_id":"A","audio_type":"song"})
    jid = create_job([sample["id"]], ["basic"])
    db.execute("UPDATE jobs SET status='running' WHERE id=?", (jid,))
    db.execute("UPDATE items SET status='running' WHERE job_id=?", (jid,))
    runner = Runner()
    runner.start()
    try:
        until = time.time() + 20
        while time.time() < until and job_view(jid)["status"] in ("queued", "running"):
            time.sleep(.1)
        assert job_view(jid)["status"] == "completed_with_errors"
        assert job_view(jid)["items"][0]["status"] == "failed"
    finally:
        runner.close()


def insert_score(sample, score):
    db.execute("INSERT INTO items(id,job_id,sample_id,metric,status,result,snapshot) VALUES(?,?,?,?,?,?,?)",
               (db.uid(), "test", sample["id"], "clap", "success", json.dumps({"value":{"score":score},"protocol":PROTOCOL}),
                json.dumps({"sample":sample,"signature":signature(sample,"clap")})))


def test_prompt_equal_weight_and_shared_pair_ci():
    ss = []
    for model, prompt, scores in (("A","p1",[0,0,0]),("A","p2",[1]),("B","p1",[.2]),("B","p2",[.8]),("B","extra",[.9])):
        for score in scores:
            s = db.insert_sample({"filename":"x.wav","path":"x","sha256":db.uid(),"prompt_id":prompt,"model_id":model,"audio_type":"instrumental"})
            insert_score(s, score)
            ss.append(s)
    data = report(ss)
    a = next(g for g in data["groups"] if g["group"][0] == "A")
    assert a["metrics"]["clap"]["mean"] == .5  # Not sample-weighted (.25).
    pair = next(p for p in data["pairs"] if p["metric"] == "clap")
    assert pair["shared_prompts"] == 2
    assert pair["delta_a_minus_b"] == pytest.approx(0)
    assert pair["ci95"] is not None


def test_cross_origin_writes_are_rejected(client):
    assert client.post('/api/demo', headers={"Origin":"https://evil.example"}).status_code == 403


def test_text_segmentation_retains_all_tokens():
    class Tokenizer:
        def encode(self, text, add_special_tokens=False): return list(map(int,text.split()))
        def decode(self, ids, **kw): return " ".join(map(str,ids))
    source = " ".join(map(str,range(1000)))
    parts = token_chunks(source, Tokenizer(), 75)
    assert " ".join(p for p,_ in parts) == source
    assert sum(n for _,n in parts) == 1000


def test_edited_prompt_excludes_stale_scores(client):
    sid = upload(client)
    s = db.one("SELECT * FROM samples WHERE id=?", (sid,))
    insert_score(s, .5)
    assert client.get('/api/report').json()["groups"][0]["metrics"]["clap"]["mean"] == .5
    client.patch('/api/samples/' + sid, json={**s,"prompt_en":"A different prompt"})
    result = client.get('/api/samples').json()[0]["results"]["clap"]
    assert result["stale"]
    assert "clap" not in client.get('/api/report').json()["groups"][0]["metrics"]


def test_queued_cancellation_and_retry(client):
    sid = upload(client)
    r = client.post('/api/jobs',json={"sample_ids":[sid],"metrics":["basic"]})
    jid = r.json()["id"]
    assert client.post(f'/api/jobs/{jid}/cancel').status_code == 200
    job = wait_job(client,jid)
    assert job["status"] == "cancelled"
    assert any(it["status"] == "cancelled" for it in job["items"])
    assert client.post(f'/api/jobs/{jid}/retry').status_code == 200
    assert wait_job(client,jid)["items"][0]["status"] == "success"


@pytest.mark.parametrize('limit,reason',[("timeout_seconds","时间限制"),("memory_limit_gb","内存限制")])
def test_resource_limits_end_item_and_persist_failure(limit,reason):
    s=db.insert_sample({"filename":"x.wav","path":"missing.wav","sha256":"x","prompt_id":"p","model_id":"A","audio_type":"song"})
    jid=create_job([s["id"]],["basic"])
    job=job_view(jid)
    config=job["config"]
    config["options"][limit]=.000001
    db.execute('UPDATE jobs SET config=? WHERE id=?',(json.dumps(config),jid))
    runner=Runner()
    runner.start()
    try:
        until=time.time()+15
        while time.time()<until and job_view(jid)["status"] in ("queued","running"):
            time.sleep(.1)
        it=job_view(jid)["items"][0]
        assert it["status"] == "failed"
        assert reason in it["reason"]
    finally:
        runner.close()


def test_one_runner_per_data_directory():
    first, second = Runner(), Runner()
    first.start()
    try:
        with pytest.raises(RuntimeError, match="已有评估服务"):
            second.start()
    finally:
        first.close()
    # OS lock is released when the first runner exits.
    second.start()
    second.close()
