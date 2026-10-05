"""Session-addressed summaries; original PDFs are not retained."""

import json
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def connect(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(directory / "reports.db", timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, summary TEXT NOT NULL, "
        "sha256 TEXT NOT NULL, expires_at TEXT NOT NULL)"
    )
    return conn


def save(directory, summary, digest):
    report_id = secrets.token_urlsafe(32)
    conn = connect(directory)
    try:
        now = datetime.now(UTC)
        conn.execute("DELETE FROM reports WHERE expires_at <= ?", (now.isoformat(),))
        conn.execute(
            "INSERT INTO reports VALUES(?,?,?,?)",
            (
                report_id,
                json.dumps(summary),
                digest,
                (now + timedelta(hours=24)).isoformat(),
            ),
        )
        conn.commit()
        return report_id
    finally:
        conn.close()


def get(directory, report_id):
    if not report_id:
        return None
    conn = connect(directory)
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE id=? AND expires_at>?",
            (report_id, datetime.now(UTC).isoformat()),
        ).fetchone()
        return (
            {"summary": json.loads(row["summary"]), "sha256": row["sha256"]}
            if row
            else None
        )
    finally:
        conn.close()
