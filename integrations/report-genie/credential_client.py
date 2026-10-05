"""Server-side MCP integration. No registry imports, database path or browser-supplied role."""

import asyncio
import os
import sys
from threading import BoundedSemaphore

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_slots = BoundedSemaphore(2)


def normalize(response: dict) -> dict:
    request_id = response.get("request_id")
    if response.get("error"):
        return {
            "status": "denied"
            if response["error"] in {"unauthorized", "not_authorized"}
            else "unavailable",
            "request_id": request_id,
        }
    result = response.get("result", {})
    status = result.get("status")
    if status == "unregistered":
        return {"status": "unregistered", "request_id": request_id}
    if result.get("binding_valid") is not True:
        return {
            "status": "invalid_binding"
            if status == "invalid_binding"
            else "unavailable",
            "request_id": request_id,
        }
    available = result.get("credential_valid") is True and status == "valid"
    checks = result.get("checks", {})
    public = result.get("public_metadata", {}) if available else {}
    return {
        "status": "verified" if available else "credential_unavailable",
        "provider_id": result.get("provider_id"),
        "credential_id": result.get("credential_id"),
        "request_id": request_id,
        "public_metadata": {
            name: public[name]
            for name in ("display_name", "profession", "jurisdiction")
            if isinstance(public.get(name), str)
        },
        "checks": {
            name: checks[name]
            for name in (
                "report_digest",
                "binding_signature",
                "credential_signature_and_time",
                "credential_version",
                "registry_status",
                "license_validity",
                "medical_accuracy",
            )
            if isinstance(checks.get(name), str)
        },
    }


async def _verify(digest: str) -> dict:
    env = {
        name: os.environ[name]
        for name in (
            "PATH",
            "SYSTEMROOT",
            "CREDENTIALGATE_API_URL",
            "CREDENTIALGATE_API_TOKEN",
        )
        if name in os.environ
    }
    params = StdioServerParameters(
        command=os.environ.get("CREDENTIALGATE_MCP_PYTHON", sys.executable),
        args=["-m", "credentialgate.mcp_server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool(
                "verify_report_binding", {"sha256": digest}
            )
            if response.isError or not isinstance(response.structuredContent, dict):
                return {"status": "unavailable"}
            return normalize(response.structuredContent)


def verify_report(digest: str) -> dict:
    if not os.environ.get("CREDENTIALGATE_API_TOKEN"):
        return {"status": "not_configured"}
    if not _slots.acquire(blocking=False):
        return {"status": "unavailable"}

    async def bounded():
        return await asyncio.wait_for(_verify(digest), timeout=15)

    try:
        return asyncio.run(bounded())
    except Exception:
        # SDK subprocess errors can contain configuration details; never reflect them to the browser.
        return {"status": "unavailable"}
    finally:
        _slots.release()
