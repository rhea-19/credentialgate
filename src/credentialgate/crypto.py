"""Ed25519 over exact UTF-8 payload bytes; no custom crypto or JCS claims."""

import base64
import json
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def encode(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def sign_payload(payload: dict, key, key_id: str) -> dict:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {
        "algorithm": "Ed25519",
        "key_id": key_id,
        "payload": encode(raw),
        "signature": encode(key.sign(raw)),
    }


def verify_payload(
    artifact: dict, trust: dict, provider_id: str, schema: str = "credentialgate.demo.v1"
) -> tuple[str, dict | None]:
    try:
        if artifact["algorithm"] != "Ed25519":
            return "invalid_signature", None
        trusted = trust.get(artifact["key_id"])
        if not trusted:
            return "untrusted_issuer", None
        raw = base64.b64decode(artifact["payload"], validate=True)
        signature = base64.b64decode(artifact["signature"], validate=True)
        key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(trusted["public_key"], validate=True)
        )
        key.verify(signature, raw)
        claims = json.loads(raw)
        if claims["issuer"] != trusted["issuer"] or claims["provider_id"] != provider_id:
            return "identity_mismatch", None
        if claims["schema"] != schema:
            return "unsupported_schema", None
        now = datetime.now(UTC)
        issued = datetime.fromisoformat(claims["issued_at"])
        expires = datetime.fromisoformat(claims["expires_at"])
        if issued > now:
            return "not_yet_valid", None
        if expires <= now:
            return "expired", None
        return "valid", claims
    except (InvalidSignature, ValueError, KeyError, TypeError, UnicodeError):
        return "invalid_artifact", None
