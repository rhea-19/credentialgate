"""SQLite persistence; audit writes are serialized with credential access."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS principals (
 token_hash TEXT PRIMARY KEY, subject TEXT NOT NULL, role TEXT NOT NULL,
 tenant TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS providers (
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, fields TEXT NOT NULL,
 artifact TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','revoked','unknown'))
);
CREATE TABLE IF NOT EXISTS trust_keys (key_id TEXT PRIMARY KEY, entry TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_bindings (
 sha256 TEXT PRIMARY KEY, provider_id TEXT NOT NULL REFERENCES providers(id),
 artifact TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT NOT NULL,
 previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
 BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
 BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def append_audit(
    conn, *, actor: str, operation: str, provider_id: str, outcome: str, request_id: str
) -> None:
    row = conn.execute("SELECT event_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
    previous = row[0] if row else "0" * 64
    event = json.dumps(
        {
            "actor": actor,
            "operation": operation,
            "provider_id": provider_id,
            "outcome": outcome,
            "request_id": request_id,
            "at": datetime.now(UTC).isoformat(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256((previous + "\n" + event).encode()).hexdigest()
    conn.execute(
        "INSERT INTO audit(event,previous_hash,event_hash) VALUES(?,?,?)", (event, previous, digest)
    )


def check_audit(path: Path) -> dict:
    conn = connect(path)
    try:
        previous = "0" * 64
        count = 0
        for row in conn.execute("SELECT * FROM audit ORDER BY id"):
            digest = hashlib.sha256((previous + "\n" + row["event"]).encode()).hexdigest()
            if row["previous_hash"] != previous or row["event_hash"] != digest:
                return {"valid": False, "broken_at": row["id"]}
            previous = digest
            count += 1
        return {"valid": True, "events": count, "head": previous}
    finally:
        conn.close()
