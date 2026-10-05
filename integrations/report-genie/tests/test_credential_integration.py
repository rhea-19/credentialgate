import hashlib
import io
import re

import pytest

from app import create_app
from credential_client import normalize


@pytest.fixture
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only",
            "DEMO_MODE": True,
            "REPORT_DATA_DIR": str(tmp_path),
        }
    )


def csrf(client):
    page = client.get("/")
    return re.search(rb'name="csrf-token" content="([^"]+)"', page.data)[1].decode()


def upload(client, raw=b"%PDF-1.4\nsynthetic\n%%EOF", name="demo.pdf"):
    token = csrf(client)
    return client.post(
        "/upload",
        data={
            "csrf_token": token,
            "pdf-upload": (io.BytesIO(raw), name),
            "report-type": "other",
        },
    )


def test_demo_page_and_real_check_uses_session_digest(app, monkeypatch):
    client = app.test_client()
    token = csrf(client)
    assert client.post("/demo", data={"csrf_token": token}).status_code == 302
    assert b"Check report evidence" in client.get("/summary").data
    seen = []
    monkeypatch.setattr(
        "credential_client.verify_report",
        lambda digest: seen.append(digest) or {"status": "unregistered"},
    )
    response = client.post(
        "/credential-check",
        headers={"X-CSRF-Token": token},
        json={"sha256": "forged", "role": "reviewer", "provider_id": "other"},
    )
    assert response.json["status"] == "unregistered"
    fixture = client.get("/demo-report.pdf").data
    assert seen == [hashlib.sha256(fixture).hexdigest()]


def test_uploads_are_isolated_between_visitors(app, monkeypatch):
    a, b = app.test_client(), app.test_client()
    first = b"%PDF-first"
    second = b"%PDF-second"
    assert upload(a, first).status_code == 302
    assert upload(b, second).status_code == 302
    monkeypatch.setattr(
        "credential_client.verify_report", lambda digest: {"digest": digest}
    )
    assert (
        a.post("/credential-check", headers={"X-CSRF-Token": csrf(a)}).json["digest"]
        == hashlib.sha256(first).hexdigest()
    )
    assert (
        b.post("/credential-check", headers={"X-CSRF-Token": csrf(b)}).json["digest"]
        == hashlib.sha256(second).hexdigest()
    )
    assert app.test_client().get("/summary").status_code == 302


def test_csrf_required(app):
    client = app.test_client()
    csrf(client)
    assert client.post("/demo").status_code == 400
    assert client.post("/credential-check").status_code == 400


def test_missing_report(app):
    client = app.test_client()
    assert (
        client.post(
            "/credential-check", headers={"X-CSRF-Token": csrf(client)}
        ).status_code
        == 404
    )


def test_unknown_file_has_no_automatic_attestation(app, monkeypatch):
    client = app.test_client()
    assert upload(client).status_code == 302
    monkeypatch.setattr(
        "credential_client.verify_report", lambda _: {"status": "unregistered"}
    )
    assert client.post(
        "/credential-check", headers={"X-CSRF-Token": csrf(client)}
    ).json == {"status": "unregistered"}


def test_invalid_upload_rejected(app):
    assert upload(app.test_client(), b"not a pdf").status_code == 400


def test_summary_does_not_contain_secrets(app, monkeypatch):
    monkeypatch.setenv("CREDENTIALGATE_API_TOKEN", "never-send-this-to-browser")
    client = app.test_client()
    upload(client)
    assert b"never-send-this-to-browser" not in client.get("/summary").data


def test_model_processing_path_preserved_and_temp_file_removed(app, monkeypatch):
    from pathlib import Path

    app.config["DEMO_MODE"] = False
    paths = []

    def process(path, report_type, notes):
        paths.append(path)
        assert Path(path).read_bytes().startswith(b"%PDF-")
        return {
            "tokens": [{"name": "Synthetic extraction", "value": "test"}],
            "notes": notes,
        }

    monkeypatch.setattr("app.process_pdf", process)
    client = app.test_client()
    assert upload(client, name="../../unsafe.pdf").status_code == 302
    assert b"Synthetic extraction" in client.get("/summary").data
    assert paths and not Path(paths[0]).exists()


def test_model_failure_cleans_temp_file(app, monkeypatch):
    from pathlib import Path

    app.config["DEMO_MODE"] = False
    paths = []

    def fail(path, *args):
        paths.append(path)
        raise RuntimeError("private exception details")

    monkeypatch.setattr("app.process_pdf", fail)
    response = upload(app.test_client())
    assert response.status_code == 503 and b"private exception" not in response.data
    assert not Path(paths[0]).exists()


def test_normalization_strips_nonpublic_fields():
    result = normalize(
        {
            "result": {
                "binding_valid": True,
                "credential_valid": True,
                "status": "valid",
                "public_metadata": {"display_name": "Demo", "date_of_birth": "private"},
            }
        }
    )
    assert result["public_metadata"] == {"display_name": "Demo"}


@pytest.mark.parametrize(
    "upstream, expected",
    [
        ({"error": "service_unavailable"}, "unavailable"),
        ({"error": "not_authorized"}, "denied"),
        ({"result": {"status": "unregistered"}}, "unregistered"),
        ({"result": {"status": "invalid_binding"}}, "invalid_binding"),
        (
            {
                "result": {
                    "status": "valid",
                    "binding_valid": "yes",
                    "credential_valid": True,
                }
            },
            "unavailable",
        ),
    ],
)
def test_failed_checks_never_become_verified(upstream, expected):
    assert normalize(upstream)["status"] == expected
