"""A real stdio MCP subprocess calls a real HTTP service with isolated test fixtures."""

import asyncio
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from credentialgate.storage import check_audit


@pytest.mark.asyncio
async def test_mcp_end_to_end(fixture_data):
    directory, tokens = fixture_data
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    source = str(Path(__file__).resolve().parents[1] / "src")
    env = {**os.environ, "PYTHONPATH": source, "CREDENTIALGATE_DATA_DIR": str(directory)}
    proc = subprocess.Popen(
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
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(100):
                if proc.poll() is not None:
                    pytest.fail(proc.stderr.read().decode())
                try:
                    if (await client.get(base + "/healthz")).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.05)
            else:
                pytest.fail("Test API did not start")
        for profile in ["public", "institution"]:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "credentialgate.mcp_server"],
                env={
                    "PYTHONPATH": source,
                    "CREDENTIALGATE_API_URL": base,
                    "CREDENTIALGATE_API_TOKEN": tokens[profile],
                },
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = (await session.list_tools()).tools
                    assert {t.name for t in tools} == {
                        "get_provider_summary",
                        "verify_credential",
                        "request_credential_fields",
                        "verify_report_binding",
                    }
                    assert all("role" not in t.inputSchema.get("properties", {}) for t in tools)
                    verified = await session.call_tool(
                        "verify_credential", {"provider_id": "prov_demo_001"}
                    )
                    assert verified.structuredContent["result"]["verified"]
                    result = await session.call_tool(
                        "request_credential_fields",
                        {"provider_id": "prov_demo_001", "fields": ["license_number"]},
                    )
                    if profile == "public":
                        assert result.structuredContent["error"] == "not_authorized"
                    else:
                        assert result.structuredContent["result"]["fields"] == {
                            "license_number": "DEMO-LICENSE-001"
                        }
        assert check_audit(directory / "credentials.db")["events"] == 4
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
