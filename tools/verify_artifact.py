"""Independent offline verifier: no imports from CredentialGate's application package."""

import argparse
import base64
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify(artifact_path: Path, trust_path: Path, expected_provider: str) -> dict:
    try:
        if artifact_path.stat().st_size > 65536 or trust_path.stat().st_size > 65536:
            raise ValueError("Input too large")
        artifact = json.loads(artifact_path.read_text())
        trust = json.loads(trust_path.read_text())
        if artifact["algorithm"] != "Ed25519":
            raise ValueError("Unsupported algorithm")
        issuer = trust[artifact["key_id"]]
        payload = base64.b64decode(artifact["payload"], validate=True)
        public = base64.b64decode(issuer["public_key"], validate=True)
        signature = base64.b64decode(artifact["signature"], validate=True)
        Ed25519PublicKey.from_public_bytes(public).verify(signature, payload)
        claims = json.loads(payload)
        now = datetime.now(UTC)
        if (
            claims["provider_id"] != expected_provider
            or claims["issuer"] != issuer["issuer"]
            or claims["schema"] != "credentialgate.demo.v1"
            or not datetime.fromisoformat(claims["issued_at"])
            <= now
            < datetime.fromisoformat(claims["expires_at"])
        ):
            raise ValueError("Identity, schema or validity mismatch")
        return {
            "verified": True,
            "provider_id": expected_provider,
            "scope": "signed public metadata only; revocation not checked offline",
        }
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature):
        return {"verified": False, "error": "artifact_verification_failed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument(
        "--trust",
        type=Path,
        required=True,
        help="Obtain this trust bundle through a trusted channel, not from the artifact",
    )
    parser.add_argument("--provider", required=True)
    args = parser.parse_args()
    result = verify(args.artifact, args.trust, args.provider)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["verified"] else 2)
