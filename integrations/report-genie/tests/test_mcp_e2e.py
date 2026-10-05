"""Run when CredentialGate is installed in the test environment; no cloud model calls."""

import io
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytest.importorskip(
    "credentialgate",
    reason="Install CredentialGate locally to exercise the full MCP service path",
)
from credentialgate.bind_report import bind_report
from credentialgate.bootstrap import seed
from credentialgate.storage import check_audit, connect

from app import create_app


def test_flask_to_real_mcp_to_credential_service(tmp_path, monkeypatch):
    registry = tmp_path / "registry"
    tokens = seed(registry)
    sample = Path(__file__).resolve().parents[1] / "resources/credential-demo.pdf"
    bind_report(sample, "prov_demo_001", registry)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    monkeypatch.setenv("CREDENTIALGATE_API_URL", base)
    monkeypatch.setenv("CREDENTIALGATE_API_TOKEN", tokens["public"])
    monkeypatch.setenv("CREDENTIALGATE_MCP_PYTHON", sys.executable)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "credentialgate.service:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env={**os.environ, "CREDENTIALGATE_DATA_DIR": str(registry)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(80):
            if process.poll() is not None:
                pytest.fail(process.stderr.read().decode())
            try:
                if (
                    httpx.get(base + "/healthz", trust_env=False, timeout=1).status_code
                    == 200
                ):
                    break
            except httpx.TransportError:
                time.sleep(0.05)
        else:
            pytest.fail("Credential API failed to start")
        app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test",
                "DEMO_MODE": True,
                "REPORT_DATA_DIR": str(tmp_path / "reports"),
            }
        )
        client = app.test_client()
        token = re.search(
            rb'name="csrf-token" content="([^"]+)"', client.get("/").data
        )[1].decode()
        assert client.post("/demo", data={"csrf_token": token}).status_code == 302
        result = client.post("/credential-check", headers={"X-CSRF-Token": token}).json
        assert result["status"] == "verified"
        assert result["checks"]["license_validity"] == "not_evaluated"
        assert "date_of_birth" not in str(result)
        changed = app.test_client()
        other_token = re.search(
            rb'name="csrf-token" content="([^"]+)"', changed.get("/").data
        )[1].decode()
        changed.post(
            "/upload",
            data={
                "csrf_token": other_token,
                "pdf-upload": (
                    io.BytesIO(sample.read_bytes() + b"\nmodified"),
                    "changed.pdf",
                ),
            },
        )
        assert (
            changed.post(
                "/credential-check", headers={"X-CSRF-Token": other_token}
            ).json["status"]
            == "unregistered"
        )
        conn = connect(registry / "credentials.db")
        conn.execute("UPDATE providers SET status='revoked'")
        conn.commit()
        result = client.post("/credential-check", headers={"X-CSRF-Token": token}).json
        assert result["status"] == "credential_unavailable"
        assert result["public_metadata"] == {}
        conn.execute(
            "CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'no'); END"
        )
        conn.commit()
        conn.close()
        assert (
            client.post("/credential-check", headers={"X-CSRF-Token": token}).json[
                "status"
            ]
            == "unavailable"
        )
        audit = check_audit(registry / "credentials.db")
        assert audit["valid"] and audit["events"] == 4
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
