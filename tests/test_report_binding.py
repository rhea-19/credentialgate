import hashlib
import json

import pytest
from conftest import bearer

from credentialgate.bind_report import bind_report
from credentialgate.storage import check_audit, connect


@pytest.fixture
def report(api, tmp_path):
    _, _, directory = api
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(b"%PDF-1.4\nsynthetic report bytes\n%%EOF")
    return bind_report(path, "prov_demo_001", directory)


def request(api, report, profile="public"):
    client, tokens, _ = api
    return client.post(
        "/v1/reports/verify", headers=bearer(tokens, profile), json={"sha256": report}
    )


def test_signed_report_association(api, report):
    response = request(api, report)
    result = response.json()["result"]
    assert response.status_code == 200
    assert result["binding_valid"] and result["credential_valid"]
    assert result["provider_id"] == "prov_demo_001"
    assert result["checks"]["license_validity"] == "not_evaluated"
    assert set(result["public_metadata"]) == {"display_name", "profession", "jurisdiction"}
    assert "date_of_birth" not in response.text and "DEMO-LICENSE" not in response.text
    assert check_audit(api[2] / "credentials.db")["events"] == 2


def test_different_bytes_do_not_inherit_association(api, report):
    changed = hashlib.sha256(b"%PDF-different").hexdigest()
    result = request(api, changed).json()["result"]
    assert result["status"] == "unregistered" and result["binding_valid"] is False
    assert "provider_id" not in result


def test_other_tenant_denied(api, report):
    response = request(api, report, "other-institution")
    assert response.status_code == 403 and "result" not in response.json()


def test_report_identity_required(api, report):
    response = api[0].post("/v1/reports/verify", json={"sha256": report})
    assert response.status_code == 401


@pytest.mark.parametrize("mutation", ["signature", "digest", "provider"])
def test_tampering_fails(api, report, mutation):
    conn = connect(api[2] / "credentials.db")
    if mutation == "signature":
        artifact = json.loads(conn.execute("SELECT artifact FROM report_bindings").fetchone()[0])
        artifact["signature"] = "AAAA"
        conn.execute("UPDATE report_bindings SET artifact=?", (json.dumps(artifact),))
    elif mutation == "digest":
        report = "1" * 64
        conn.execute("UPDATE report_bindings SET sha256=?", (report,))
    else:
        conn.execute("UPDATE report_bindings SET provider_id='prov_demo_002'")
    conn.commit()
    conn.close()
    result = request(api, report).json()["result"]
    assert result["status"] == "invalid_binding" and result["binding_valid"] is False
    assert "public_metadata" not in result


def test_revocation_distinct_from_report_integrity(api, report):
    conn = connect(api[2] / "credentials.db")
    conn.execute("UPDATE providers SET status='revoked'")
    conn.commit()
    conn.close()
    result = request(api, report).json()["result"]
    assert result["binding_valid"] is True and result["credential_valid"] is False
    assert result["checks"]["registry_status"] == "revoked"
    assert "public_metadata" not in result


def test_report_audit_failure_returns_no_verification(api, report):
    conn = connect(api[2] / "credentials.db")
    conn.execute(
        "CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'no'); END"
    )
    conn.commit()
    conn.close()
    response = request(api, report)
    assert response.status_code == 503 and "result" not in response.json()


def test_report_role_override_rejected(api, report):
    client, tokens, _ = api
    assert (
        client.post(
            "/v1/reports/verify",
            headers=bearer(tokens, "public"),
            json={"sha256": report, "role": "reviewer"},
        ).status_code
        == 422
    )


def test_operator_cannot_silently_reassign(api, tmp_path, report):
    path = tmp_path / "synthetic.pdf"
    with pytest.raises(ValueError, match="another provider"):
        bind_report(path, "prov_demo_002", api[2])
