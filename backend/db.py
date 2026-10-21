import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import DB


def uid():
    return uuid.uuid4().hex


@contextmanager
def connect():
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with connect() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS samples (
          id TEXT PRIMARY KEY, filename TEXT NOT NULL, path TEXT NOT NULL,
          sha256 TEXT NOT NULL, prompt_id TEXT NOT NULL, prompt TEXT NOT NULL DEFAULT '',
          prompt_en TEXT NOT NULL DEFAULT '', translation_source TEXT NOT NULL DEFAULT '',
          model_id TEXT NOT NULL, model_version TEXT NOT NULL DEFAULT '',
          audio_type TEXT NOT NULL, seed TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '',
          role TEXT NOT NULL DEFAULT 'generated', created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, status TEXT NOT NULL, config TEXT NOT NULL,
          created REAL NOT NULL, updated REAL NOT NULL, cancel INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS items (
          id TEXT PRIMARY KEY, job_id TEXT NOT NULL, sample_id TEXT NOT NULL,
          metric TEXT NOT NULL, status TEXT NOT NULL, result TEXT, reason TEXT,
          elapsed REAL, peak_mb REAL, cache_key TEXT, snapshot TEXT NOT NULL,
          FOREIGN KEY(job_id) REFERENCES jobs(id));
        CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY, a TEXT NOT NULL, b TEXT NOT NULL,
          revealed INTEGER NOT NULL DEFAULT 0, choice TEXT, note TEXT, created REAL NOT NULL);
        """)


def rows(sql, args=()):
    with connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql, args=()):
    r = rows(sql, args)
    return r[0] if r else None


def execute(sql, args=()):
    with connect() as c:
        c.execute(sql, args)


def insert_sample(values):
    values = {"id": uid(), "created": time.time(), "prompt": "", "prompt_en": "",
              "translation_source": "", "model_version": "", "seed": "", "tags": "", "role": "generated", **values}
    keys = list(values)
    execute(f"INSERT INTO samples ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", list(values.values()))
    return values


def decode_item(item):
    if item and item.get("result"):
        item["result"] = json.loads(item["result"])
    if item:
        item["snapshot"] = json.loads(item["snapshot"])
    return item
