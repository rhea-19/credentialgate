"""The only runtime component allowed to read credentials and decide disclosure."""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import storage
from .crypto import verify_payload
from .policy import PUBLIC_FIELDS, authorize
from .reports import check_report

FieldName = Literal[
    "display_name",
    "profession",
    "jurisdiction",
    "license_number",
    "institution",
    "license_expires_at",
    "contact_email",
    "date_of_birth",
]


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(pattern=r"^prov_[a-zA-Z0-9_]{1,64}$")


class FieldsRequest(ProviderRequest):
    fields: list[FieldName] = Field(min_length=1, max_length=8)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def create_app(data_dir: Path | None = None) -> FastAPI:
    directory = data_dir or Path(os.environ.get("CREDENTIALGATE_DATA_DIR", "var"))
    db = directory / "credentials.db"
    app = FastAPI(
        title="CredentialGate",
        version="0.1.0",
        description="Synthetic credential authorization and verification prototype.",
    )

    def execute(
        operation: str, request: ProviderRequest | ReportRequest | None, authorization: str | None
    ):
        request_id = str(uuid.uuid4())
        audit_provider = getattr(request, "provider_id", "unresolved")
        conn = None
        try:
            if not db.is_file():
                raise sqlite3.OperationalError("Service not initialized")
            conn = storage.connect(db)
            # The read, access decision and audit insertion share one serialized transaction.
            conn.execute("BEGIN IMMEDIATE")
            principal = None
            if authorization and authorization.startswith("Bearer "):
                digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
                row = conn.execute(
                    "SELECT * FROM principals WHERE token_hash=?", (digest,)
                ).fetchone()
                if row and datetime.fromisoformat(row["expires_at"]) > datetime.now(UTC):
                    principal = dict(row)
            actor = principal["subject"] if principal else "unauthenticated"
            code, outcome, result = 401, "unauthorized", None
            if request is None:
                code, outcome = 422, "invalid_request"
            elif principal and isinstance(request, ReportRequest):
                code, outcome, result, audit_provider = check_report(
                    conn, principal, request.sha256
                )
            elif principal:
                row = conn.execute(
                    "SELECT * FROM providers WHERE id=?", (request.provider_id,)
                ).fetchone()
                requested = (
                    request.fields if isinstance(request, FieldsRequest) else sorted(PUBLIC_FIELDS)
                )
                if not row or not authorize(principal, row["tenant"], requested):
                    # Do not reveal existence to an out-of-scope caller.
                    code, outcome = 403, "not_authorized"
                else:
                    trust = {
                        r["key_id"]: json.loads(r["entry"])
                        for r in conn.execute("SELECT * FROM trust_keys")
                    }
                    integrity, claims = verify_payload(
                        json.loads(row["artifact"]), trust, row["id"]
                    )
                    status = integrity if integrity != "valid" else row["status"]
                    if operation == "verify":
                        code, outcome = (
                            200,
                            "verified" if status == "active" else "verification_failed",
                        )
                        result = {
                            "provider_id": row["id"],
                            "verified": status == "active",
                            "status": "valid" if status == "active" else status,
                            "scope": "signed public metadata; live registry status",
                        }
                    elif status != "active":
                        code, outcome = 409, "credential_unavailable"
                    else:
                        # Public claims come from the verified bytes, never an unsigned duplicate.
                        values = {**json.loads(row["fields"]), **claims["public_metadata"]}
                        result = {
                            "provider_id": row["id"],
                            "fields": {name: values[name] for name in requested},
                            "assurance": "Public metadata is signed. Restricted fields are registry assertions.",
                        }
                        code, outcome = 200, "disclosed"
            storage.append_audit(
                conn,
                actor=actor,
                operation=operation,
                provider_id=audit_provider if request else "invalid",
                outcome=outcome,
                request_id=request_id,
            )
            conn.commit()  # Nothing leaves the service before the audit transaction commits.
            body = {"request_id": request_id}
            body["result" if code == 200 else "error"] = result if code == 200 else outcome
            return JSONResponse(body, status_code=code, headers={"Cache-Control": "no-store"})
        except (sqlite3.Error, ValueError, KeyError, TypeError):
            if conn:
                conn.rollback()
            return JSONResponse(
                {"error": "service_unavailable", "request_id": request_id},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        finally:
            if conn:
                conn.close()

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Avoid FastAPI's default reflection of untrusted request values in error bodies.
        from starlette.concurrency import run_in_threadpool

        return await run_in_threadpool(
            execute, "invalid_request", None, request.headers.get("authorization")
        )

    @app.get("/healthz")
    def health():
        return {"status": "ok", "mode": "synthetic-prototype"}

    @app.post("/v1/summary")
    def summary(request: ProviderRequest, authorization: str | None = Header(default=None)):
        return execute("summary", request, authorization)

    @app.post("/v1/verify")
    def verify(request: ProviderRequest, authorization: str | None = Header(default=None)):
        return execute("verify", request, authorization)

    @app.post("/v1/fields")
    def fields(request: FieldsRequest, authorization: str | None = Header(default=None)):
        return execute("fields", request, authorization)

    @app.post("/v1/reports/verify")
    def report(request: ReportRequest, authorization: str | None = Header(default=None)):
        return execute("report_verify", request, authorization)

    return app


app = create_app()
