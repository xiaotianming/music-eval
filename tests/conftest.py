import os
import tempfile
os.environ["MUSIC_EVAL_DATA"] = tempfile.mkdtemp(prefix="music-eval-tests-")

import pytest
from fastapi.testclient import TestClient
from backend import db
from backend.app import app


@pytest.fixture(autouse=True)
def clean_database():
    db.init_db()
    with db.connect() as c:
        for table in ("samples", "jobs", "items", "cache", "sessions"):
            c.execute(f"DELETE FROM {table}")
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
