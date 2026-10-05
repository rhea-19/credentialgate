import base64
import json
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from credentialgate.bootstrap import seed
from credentialgate.crypto import encode, sign_payload, verify_payload
from credentialgate.storage import append_audit, check_audit, connect

ROOT = Path(__file__).resolve().parents[1]


def test_persistent_ids_and_no_reseed(fixture_data):
    directory, _ = fixture_data
    with pytest.raises(FileExistsError):
        seed(directory)
    for _ in range(2):
        conn = connect(directory / "credentials.db")
        assert conn.execute("SELECT id FROM providers ORDER BY id").fetchone()[0] == "prov_demo_001"
        conn.close()


@pytest.mark.parametrize("mutation", ["none", "tamper", "identity", "issuer", "expired", "future"])
def test_online_and_independent_verifier(tmp_path, mutation):
    key = Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    payload = {
        "provider_id": "prov_test",
        "issuer": "issuer-a",
        "schema": "credentialgate.demo.v1",
        "issued_at": (now - timedelta(days=1)).isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "public_metadata": {},
    }
    if mutation == "identity":
        payload["provider_id"] = "prov_other"
    if mutation == "issuer":
        payload["issuer"] = "untrusted"
    if mutation == "expired":
        payload["expires_at"] = (now - timedelta(hours=1)).isoformat()
    if mutation == "future":
        payload["issued_at"] = (now + timedelta(hours=1)).isoformat()
    artifact = sign_payload(payload, key, "key-1")
    trust = {
        "key-1": {"issuer": "issuer-a", "public_key": encode(key.public_key().public_bytes_raw())}
    }
    if mutation == "tamper":
        artifact["payload"] = encode(b'{"provider_id":"forged"}')
    status, _ = verify_payload(artifact, trust, "prov_test")
    assert (status == "valid") == (mutation == "none")
    artifact_path, trust_path = tmp_path / "artifact.json", tmp_path / "trust.json"
    artifact_path.write_text(json.dumps(artifact))
    trust_path.write_text(json.dumps(trust))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/verify_artifact.py"),
            str(artifact_path),
            "--trust",
            str(trust_path),
            "--provider",
            "prov_test",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == (0 if mutation == "none" else 2)
    assert json.loads(result.stdout)["verified"] == (mutation == "none")


def test_artifact_has_only_public_metadata(fixture_data):
    directory, _ = fixture_data
    artifact = json.loads((directory / "prov_demo_001.credential.json").read_text())
    claims = json.loads(base64.b64decode(artifact["payload"]))
    assert set(claims["public_metadata"]) == {"display_name", "profession", "jurisdiction"}
    assert "1990" not in json.dumps(claims) and "DEMO-LICENSE" not in json.dumps(claims)
    assert verify_payload(artifact, {}, "prov_demo_001")[0] == "untrusted_issuer"


def test_immutable_audit_and_tamper_detection(fixture_data):
    directory, _ = fixture_data
    db = directory / "credentials.db"
    conn = connect(db)
    conn.execute("BEGIN IMMEDIATE")
    append_audit(
        conn,
        actor="test",
        operation="summary",
        provider_id="prov_demo_001",
        outcome="disclosed",
        request_id="test-id",
    )
    conn.commit()
    for sql in ["DELETE FROM audit", "UPDATE audit SET event='tampered'"]:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute(sql)
        conn.rollback()
    assert check_audit(db)["valid"]
    # Negative control: an administrator bypasses a trigger; the checker detects modified content.
    conn.execute("DROP TRIGGER audit_no_update")
    conn.execute("UPDATE audit SET event='tampered'")
    conn.commit()
    conn.close()
    assert check_audit(db) == {"valid": False, "broken_at": 1}
