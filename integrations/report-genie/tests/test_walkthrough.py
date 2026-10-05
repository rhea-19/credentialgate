import hashlib
import re

from app import create_app, demo_pdf


def make_client(tmp_path, enabled=True):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DEMO_MODE": enabled,
            "REPORT_DATA_DIR": str(tmp_path),
        }
    ).test_client()


def test_walkthrough_examples_use_distinct_real_pdf_bytes(tmp_path, monkeypatch):
    client = make_client(tmp_path)
    page = client.get("/walkthrough")
    assert page.status_code == 200 and b"What can we confirm" in page.data
    token = re.search(rb'name="csrf-token" content="([^"]+)"', page.data)[1].decode()
    observed = []
    monkeypatch.setattr(
        "credential_client.verify_report",
        lambda digest: observed.append(digest) or {"status": "unregistered"},
    )
    for scenario in ["registered", "changed"]:
        response = client.post(
            "/demo",
            data={"csrf_token": token, "scenario": scenario, "view": "walkthrough"},
        )
        assert response.location == "/walkthrough"
        assert b"Check this report" in client.get("/walkthrough").data
        client.post("/credential-check", headers={"X-CSRF-Token": token})
        download = client.get(f"/demo-report.pdf?scenario={scenario}")
        assert download.data == demo_pdf(scenario)
        assert observed[-1] == hashlib.sha256(download.data).hexdigest()
    assert observed[0] != observed[1]
    assert len(demo_pdf("registered")) == len(demo_pdf("changed"))


def test_walkthrough_does_not_expose_last_uploaded_report(tmp_path):
    client = make_client(tmp_path)
    with client.session_transaction() as session:
        session["report_id"] = "missing"
    response = client.get("/walkthrough")
    assert (
        b"Choose an example" in response.data
        and b'id="run-walkthrough"' not in response.data
    )


def test_walkthrough_disabled_outside_demo_mode(tmp_path):
    client = make_client(tmp_path, False)
    assert client.get("/walkthrough").status_code == 404
    assert client.get("/demo-report.pdf?scenario=changed").status_code == 404


def test_unknown_scenario_cannot_be_selected(tmp_path):
    client = make_client(tmp_path)
    client.get("/")
    with client.session_transaction() as session:
        token = session["csrf"]
    assert (
        client.post(
            "/demo", data={"csrf_token": token, "scenario": "arbitrary"}
        ).status_code
        == 400
    )
    assert client.get("/demo-report.pdf?scenario=arbitrary").status_code == 400
