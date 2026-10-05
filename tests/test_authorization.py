import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import bearer

from credentialgate import storage


@pytest.mark.parametrize(
    "profile,field,expected",
    [
        ("public", "display_name", 200),
        ("public", "license_number", 403),
        ("public", "date_of_birth", 403),
        ("institution", "license_number", 200),
        ("institution", "contact_email", 403),
        ("reviewer", "date_of_birth", 200),
        ("other-institution", "license_number", 403),
    ],
)
def test_disclosure_matrix(api, profile, field, expected):
    client, tokens, directory = api
    response = client.post(
        "/v1/fields",
        headers=bearer(tokens, profile),
        json={"provider_id": "prov_demo_001", "fields": [field]},
    )
    assert response.status_code == expected
    if expected == 200:
        assert set(response.json()["result"]["fields"]) == {field}
    else:
        assert "result" not in response.json()
        assert "1990" not in response.text and "DEMO-LICENSE" not in response.text
    assert storage.check_audit(directory / "credentials.db")["events"] == 1


def test_mixed_request_is_all_or_nothing(api):
    client, tokens, _ = api
    response = client.post(
        "/v1/fields",
        headers=bearer(tokens, "public"),
        json={"provider_id": "prov_demo_001", "fields": ["display_name", "date_of_birth"]},
    )
    assert response.status_code == 403
    assert "Dr. Demo" not in response.text


def test_role_spoofing_rejected_and_audited(api):
    client, tokens, directory = api
    response = client.post(
        "/v1/fields",
        headers=bearer(tokens, "public"),
        json={"provider_id": "prov_demo_001", "fields": ["date_of_birth"], "role": "reviewer"},
    )
    assert response.status_code == 422
    assert "reviewer" not in response.text
    assert storage.check_audit(directory / "credentials.db")["events"] == 1


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer bogus"}])
def test_missing_or_invalid_identity(api, headers):
    client, _, directory = api
    assert (
        client.post(
            "/v1/summary", headers=headers, json={"provider_id": "prov_demo_001"}
        ).status_code
        == 401
    )
    assert storage.check_audit(directory / "credentials.db")["events"] == 1


def test_expired_identity(api):
    client, tokens, directory = api
    conn = storage.connect(directory / "credentials.db")
    conn.execute("UPDATE principals SET expires_at='2000-01-01T00:00:00+00:00'")
    conn.commit()
    conn.close()
    assert (
        client.post(
            "/v1/summary", headers=bearer(tokens, "public"), json={"provider_id": "prov_demo_001"}
        ).status_code
        == 401
    )


def test_tenant_scope_and_existence(api):
    client, tokens, _ = api
    for provider in ["prov_demo_001", "prov_missing"]:
        response = client.post(
            "/v1/summary",
            headers=bearer(tokens, "other-institution"),
            json={"provider_id": provider},
        )
        assert response.status_code == 403
        assert response.json()["error"] == "not_authorized"
    response = client.post(
        "/v1/fields",
        headers=bearer(tokens, "other-institution"),
        json={"provider_id": "prov_demo_002", "fields": ["license_number"]},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("status", ["revoked", "unknown"])
def test_status_fails_closed(api, status):
    client, tokens, directory = api
    conn = storage.connect(directory / "credentials.db")
    conn.execute("UPDATE providers SET status=?", (status,))
    conn.commit()
    conn.close()
    headers = bearer(tokens, "public")
    payload = {"provider_id": "prov_demo_001"}
    assert client.post("/v1/summary", headers=headers, json=payload).status_code == 409
    result = client.post("/v1/verify", headers=headers, json=payload).json()["result"]
    assert result["verified"] is False and result["status"] == status


def test_audit_failure_returns_no_data(api):
    client, tokens, directory = api
    conn = storage.connect(directory / "credentials.db")
    conn.execute(
        "CREATE TRIGGER simulate_failure BEFORE INSERT ON audit "
        "BEGIN SELECT RAISE(ABORT, 'disk unavailable'); END"
    )
    conn.commit()
    conn.close()
    response = client.post(
        "/v1/fields",
        headers=bearer(tokens, "reviewer"),
        json={"provider_id": "prov_demo_001", "fields": ["date_of_birth"]},
    )
    assert response.status_code == 503
    assert "result" not in response.json() and "1990" not in response.text


def test_concurrent_access_chain_and_secret_redaction(api):
    client, tokens, directory = api

    def request(_):
        return client.post(
            "/v1/summary", headers=bearer(tokens, "public"), json={"provider_id": "prov_demo_001"}
        ).status_code

    with ThreadPoolExecutor(max_workers=5) as pool:
        assert list(pool.map(request, range(15))) == [200] * 15
    chain = storage.check_audit(directory / "credentials.db")
    assert chain["valid"] and chain["events"] == 15
    conn = storage.connect(directory / "credentials.db")
    events = json.dumps([dict(row) for row in conn.execute("SELECT * FROM audit")])
    conn.close()
    assert all(token not in events for token in tokens.values())
    assert "Dr. Demo" not in events and "date_of_birth" not in events
