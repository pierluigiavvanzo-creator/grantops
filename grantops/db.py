from contextlib import contextmanager
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    coordinator TEXT NOT NULL,
    programme TEXT NOT NULL DEFAULT 'Horizon Europe',
    start_date TEXT,
    end_date TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    source_url TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grant_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    byte_count INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'STAGED_NOT_PARSED',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    record_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    owner TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    source_page TEXT,
    source_section TEXT,
    source_quote TEXT,
    source_text_sha256 TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    obligation_id INTEGER NOT NULL REFERENCES obligations(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    evidence_type TEXT NOT NULL DEFAULT 'DOCUMENT',
    location TEXT,
    status TEXT NOT NULL DEFAULT 'MISSING',
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect(db_path: str | Path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")

    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def init_db(db_path: str | Path) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA)

def log(con, project_id, event_type, detail, entity_type=None, entity_id=None):
    con.execute(
        """INSERT INTO audit_log(
            project_id,
            event_type,
            entity_type,
            entity_id,
            detail,
            created_at
        )
        VALUES(?,?,?,?,?,?)""",
        (
            project_id,
            event_type,
            entity_type,
            entity_id,
            detail,
            utc_now()
        ),
    )

# Backward-compatible aliases used by repo.py
now = utc_now
audit = log