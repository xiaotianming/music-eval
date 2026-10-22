import copy
import csv
import io
import json
import time
import pytest
from backend import db
from backend.jobs import signature
from backend.scoring import overall_score, DIMENSIONS


def item(value):
    return {"status": "success", "stale": False, "result": {"value": value}}


def full_results():
    return {"songeval": item({"scores": {name: 4 for name in DIMENSIONS}}),
            "clap": item({"score": .5}),
            "basic": item({"silence_ratio": 0, "near_full_scale_ratio": 0, "invalid_values": 0,
                           "loudness_lufs": -14, "duration": 30})}


def test_weighted_full_score_and_bounds():
    values = full_results()
    score = overall_score(values, "song")
    assert score["score"] == 76  # 80*.7 + 50*.2 + 100*.1
    assert score["status"] == "complete" and score["coverage"] == 100
    assert sum(c["contribution"] for c in score["components"]) == pytest.approx(76)
    assert score["version"] == "overall-v1"
    values["songeval"]["result"]["value"]["scores"] = {name: 5 for name in DIMENSIONS}
    values["clap"]["result"]["value"]["score"] = 1
    assert overall_score(values, "song")["score"] == 100
    values["clap"]["result"]["value"]["score"] = -.5
    assert overall_score(values, "song")["components"][1]["score"] == 0
    before = copy.deepcopy(values)
    overall_score(values, "song")
    assert values == before


def test_missing_failed_and_stale_are_marked_partial():
    values = full_results()
    values["clap"]["stale"] = True
    score = overall_score(values, "song")
    assert score["status"] == "partial" and score["coverage"] == 80
    assert score["score"] == 82.5
    assert score["missing"] == ["提示词匹配"]
    values["clap"] = {"status": "failed", "reason": "下载失败"}
    assert overall_score(values, "song")["components"][1]["reason"] == "下载失败"
    only = overall_score({"songeval": full_results()["songeval"]}, "song")
    assert only["score"] == 80 and only["coverage"] == 70 and only["status"] == "partial"
    empty = overall_score({}, "song")
    assert empty["score"] is None and empty["status"] == "unavailable"


def test_instrumental_uses_four_dimensions():
    values = full_results()
    values["songeval"]["result"]["value"]["scores"]["Naturalness"] = None
    score = overall_score(values, "instrumental")
    assert score["score"] == 76 and score["status"] == "complete" and score["exploratory"]
    assert overall_score(values, "song")["status"] == "partial"


def test_health_penalties_and_invalid_audio():
    values = full_results()
    basic = values["basic"]["result"]["value"]
    basic["silence_ratio"] = .1
    assert overall_score(values, "song")["components"][2]["score"] == 100
    basic.update(silence_ratio=.6, near_full_scale_ratio=.01)
    assert overall_score(values, "song")["components"][2]["score"] == 0
    assert overall_score(values, "song")["score"] == 66
    basic["silence_ratio"] = 1
    assert overall_score(values, "song")["status"] == "invalid"
    assert overall_score(values, "song")["score"] is None
    basic.update(silence_ratio=0, invalid_values=1)
    assert overall_score(values, "song")["score"] is None


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), 1.5, -1.5, None])
def test_invalid_clap_does_not_produce_nonfinite_total(bad):
    values = full_results()
    values["clap"]["result"]["value"]["score"] = bad
    score = overall_score(values, "song")
    assert score["status"] == "partial" and score["score"] == 82.5


def test_fad_is_not_used_for_single_song_score():
    values = full_results()
    values["fad"] = item({"score": 10000})
    assert overall_score(values, "song")["score"] == 76


def test_api_reports_jobs_exports_and_aggregation_share_score(client):
    sample = db.insert_sample({"filename": "score-fixture.wav", "path": "fixture.wav", "sha256": "fixture",
                               "prompt_id": "p1", "model_id": "A", "audio_type": "song"})
    jid = db.uid()
    db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,0)", (jid, "completed", "{}", time.time(), time.time()))
    for metric, source in full_results().items():
        db.execute("INSERT INTO items(id,job_id,sample_id,metric,status,result,snapshot) VALUES(?,?,?,?,?,?,?)",
                   (db.uid(), jid, sample["id"], metric, "success", json.dumps(source["result"]),
                    json.dumps({"sample": sample, "signature": signature(sample, metric)})))
    sid = sample["id"]
    assert client.get('/api/samples').json()[0]["overall"]["score"] == 76
    assert client.get(f'/api/jobs/{jid}').json()["overall_scores"][sid]["score"] == 76
    latest = client.get(f'/api/samples/{sid}/report').json()
    assert latest["overall"]["score"] == 76
    assert latest["metrics"]["overall_score"] == 76
    data = client.get('/api/report').json()
    assert data["groups"][0]["metrics"]["overall_score"]["mean"] == 76
    assert '76.0 / 100' in client.get(f'/api/samples/{sid}/report/html').text
    rows = list(csv.DictReader(io.StringIO(client.get('/api/export/csv').text.lstrip('\ufeff'))))
    row = next(r for r in rows if r["metric"] == "overall_score")
    assert json.loads(row["value"])["score"] == 76
    client.patch(f'/api/samples/{sid}', json={**sample, "prompt_en": "Changed prompt"})
    assert client.get(f'/api/samples/{sid}/report').json()["overall"]["status"] == "partial"
    frozen = client.get(f'/api/samples/{sid}/report?job_id={jid}').json()
    assert frozen["overall"]["score"] == 76
    assert "overall_score" not in client.get('/api/report').json()["groups"][0]["metrics"]
