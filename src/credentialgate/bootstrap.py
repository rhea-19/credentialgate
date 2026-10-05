"""Create synthetic fixtures once. Signing keys are not kept by the running service."""

import argparse
import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .crypto import encode, sign_payload
from .storage import SCHEMA, connect


def seed(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = directory / "credentials.db"
    if db.exists():
        raise FileExistsError("Demo already initialized; choose a new data directory to reseed.")
    conn = connect(db)
    os.chmod(db, 0o600)
    conn.executescript(SCHEMA)
    key = Ed25519PrivateKey.generate()
    issuer = "urn:credentialgate:synthetic-issuer"
    kid = "demo-ed25519-1"
    trust = {kid: {"issuer": issuer, "public_key": encode(key.public_key().public_bytes_raw())}}
    conn.execute("INSERT INTO trust_keys VALUES(?,?)", (kid, json.dumps(trust[kid])))
    now = datetime.now(UTC)
    tokens = {}
    for name, role, tenant in [
        ("public", "public", ""),
        ("institution", "institution", "demo-hospital-a"),
        ("reviewer", "reviewer", "demo-hospital-a"),
        ("other-institution", "institution", "demo-hospital-b"),
    ]:
        token = secrets.token_urlsafe(32)
        tokens[name] = token
        conn.execute(
            "INSERT INTO principals VALUES(?,?,?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                name,
                role,
                tenant,
                (now + timedelta(days=30)).isoformat(),
            ),
        )
    for n, tenant in [(1, "demo-hospital-a"), (2, "demo-hospital-b")]:
        provider_id = f"prov_demo_{n:03}"
        public = {
            "display_name": f"Dr. Demo Provider {n}",
            "profession": "Physician (synthetic)",
            "jurisdiction": "Demo jurisdiction",
        }
        fields = {
            **public,
            "license_number": f"DEMO-LICENSE-{n:03}",
            "institution": tenant,
            "license_expires_at": (now + timedelta(days=365)).date().isoformat(),
            "contact_email": f"provider{n}@example.invalid",
            "date_of_birth": "1990-01-01",
        }
        payload = {
            "schema": "credentialgate.demo.v1",
            "provider_id": provider_id,
            "credential_id": f"cred_demo_{n:03}",
            "issuer": issuer,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(days=365)).isoformat(),
            "public_metadata": public,
        }
        artifact = sign_payload(payload, key, kid)
        conn.execute(
            "INSERT INTO providers VALUES(?,?,?,?,?)",
            (provider_id, tenant, json.dumps(fields), json.dumps(artifact), "active"),
        )
        (directory / f"{provider_id}.credential.json").write_text(json.dumps(artifact, indent=2))
    conn.commit()
    conn.close()
    (directory / "trust.json").write_text(json.dumps(trust, indent=2))
    secret_file = directory / "clients.json"
    secret_file.write_text(json.dumps(tokens, indent=2))
    os.chmod(secret_file, 0o600)
    return tokens


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("var"))
    args = parser.parse_args()
    seed(args.data_dir)
    print(f"Synthetic demo initialized in {args.data_dir.resolve()}. Tokens are in clients.json.")
