"""Local operator command to attest a synthetic report association; never an MCP tool."""

import argparse
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .crypto import encode, sign_payload, verify_payload
from .storage import SCHEMA, append_audit, connect


def bind_report(path: Path, provider_id: str, data_dir: Path) -> str:
    db = data_dir / "credentials.db"
    if not db.is_file():
        raise ValueError("Initialize the synthetic registry first")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Demo report must be smaller than 10 MiB")
    raw = path.read_bytes()
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Expected a synthetic PDF")
    digest = hashlib.sha256(raw).hexdigest()
    conn = connect(db)
    try:
        conn.executescript(SCHEMA)  # Additive migration for pre-integration demo databases.
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT provider_id FROM report_bindings WHERE sha256=?", (digest,)
        ).fetchone()
        if existing:
            if existing["provider_id"] != provider_id:
                raise ValueError("Report already associated with another provider")
            conn.rollback()
            return digest
        row = conn.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        trust = {
            r["key_id"]: json.loads(r["entry"]) for r in conn.execute("SELECT * FROM trust_keys")
        }
        status, claims = (
            verify_payload(json.loads(row["artifact"]), trust, provider_id)
            if row
            else ("missing", None)
        )
        if status != "valid" or row["status"] != "active":
            raise ValueError("Provider needs an active, verified credential")
        key = Ed25519PrivateKey.generate()
        kid = f"report-attestor-{uuid.uuid4().hex}"
        issuer = "urn:credentialgate:synthetic-report-attestor"
        entry = {"issuer": issuer, "public_key": encode(key.public_key().public_bytes_raw())}
        now = datetime.now(UTC)
        payload = {
            "schema": "credentialgate.report-binding.v1",
            "provider_id": provider_id,
            "credential_id": claims["credential_id"],
            "report_sha256": digest,
            "issuer": issuer,
            "issued_at": now.isoformat(),
            "expires_at": min(
                now + timedelta(days=30), datetime.fromisoformat(claims["expires_at"])
            ).isoformat(),
        }
        artifact = sign_payload(payload, key, kid)
        conn.execute("INSERT INTO trust_keys VALUES(?,?)", (kid, json.dumps(entry)))
        conn.execute(
            "INSERT INTO report_bindings VALUES(?,?,?)", (digest, provider_id, json.dumps(artifact))
        )
        append_audit(
            conn,
            actor="local-demo-operator",
            operation="bind_report",
            provider_id=provider_id,
            outcome="association_registered",
            request_id=str(uuid.uuid4()),
        )
        conn.commit()
        return digest
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("var"))
    args = parser.parse_args()
    print(
        "Registered synthetic report SHA-256:",
        bind_report(args.report, args.provider, args.data_dir),
    )
