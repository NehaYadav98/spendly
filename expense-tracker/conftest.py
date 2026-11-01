import pytest

from app import app as flask_app
from database import db


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return flask_app
