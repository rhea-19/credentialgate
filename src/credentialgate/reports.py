"""Verify operator-attested report associations inside the credential service."""

import json

from .crypto import verify_payload
from .policy import PUBLIC_FIELDS, authorize

SCOPE = (
    "Operator-attested association of report bytes with a synthetic provider credential. "
    "Does not establish authorship, license validity or medical accuracy."
)


def check_report(conn, principal: dict, digest: str):
    binding = conn.execute("SELECT * FROM report_bindings WHERE sha256=?", (digest,)).fetchone()
    if not binding:
        return (
            200,
            "report_unregistered",
            {"binding_valid": False, "status": "unregistered", "scope": SCOPE},
            "unresolved",
        )
    provider = conn.execute(
        "SELECT * FROM providers WHERE id=?", (binding["provider_id"],)
    ).fetchone()
    if not provider or not authorize(principal, provider["tenant"], sorted(PUBLIC_FIELDS)):
        return 403, "not_authorized", None, "restricted"
    trust = {r["key_id"]: json.loads(r["entry"]) for r in conn.execute("SELECT * FROM trust_keys")}
    status, report_claims = verify_payload(
        json.loads(binding["artifact"]), trust, provider["id"], "credentialgate.report-binding.v1"
    )
    if status != "valid" or report_claims.get("report_sha256") != digest:
        return (
            200,
            "report_verification_failed",
            {"binding_valid": False, "status": "invalid_binding", "scope": SCOPE},
            provider["id"],
        )
    integrity, credential = verify_payload(json.loads(provider["artifact"]), trust, provider["id"])
    current = integrity == "valid" and credential.get("credential_id") == report_claims.get(
        "credential_id"
    )
    credential_ok = current and provider["status"] == "active"
    result = {
        "binding_valid": True,
        "status": "valid" if credential_ok else "credential_unavailable",
        "provider_id": provider["id"],
        "credential_id": report_claims["credential_id"],
        "attestor": report_claims["issuer"],
        "credential_valid": credential_ok,
        "checks": {
            "report_digest": "matched",
            "binding_signature": "valid",
            "credential_signature_and_time": integrity,
            "credential_version": "matched" if current else "unavailable_or_changed",
            "registry_status": provider["status"],
            "license_validity": "not_evaluated",
            "medical_accuracy": "not_evaluated",
        },
        "scope": SCOPE,
    }
    if credential_ok:
        result["public_metadata"] = {
            field: credential["public_metadata"][field] for field in PUBLIC_FIELDS
        }
    return (
        200,
        "report_verified" if credential_ok else "report_credential_unavailable",
        result,
        provider["id"],
    )
