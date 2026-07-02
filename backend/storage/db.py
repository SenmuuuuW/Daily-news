from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

from config import BASE_DIR, settings


def database_path() -> Path:
    parsed = urlparse(settings.database_url)
    if parsed.scheme != "sqlite":
        raise ValueError("MVP supports sqlite database_url only")
    raw_path = settings.database_url.removeprefix("sqlite:///")
    path = Path(raw_path)
    return path if path.is_absolute() else BASE_DIR / path


def init_db() -> None:
    db_path = database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = (BASE_DIR / "storage" / "schema.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
    print(f"Initialized SQLite database at {db_path}")


@contextmanager
def get_connection():
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
