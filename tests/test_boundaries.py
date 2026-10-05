"""Executable dependency boundary, including a negative control for the guard."""

import ast
from pathlib import Path


def forbidden_imports(source: str) -> list[str]:
    allowed = {
        "argparse",
        "asyncio",
        "json",
        "os",
        "sys",
        "typing",
        "urllib",
        "httpx",
        "mcp",
        "anthropic",
    }
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            violations.extend(n.name for n in node.names if n.name.split(".")[0] not in allowed)
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module or node.module.split(".")[0] not in allowed:
                violations.append(node.module or "relative import")
    return violations


def test_agent_and_adapter_cannot_import_service_internals():
    src = Path(__file__).resolve().parents[1] / "src/credentialgate"
    for name in ["mcp_server.py", "client.py"]:
        assert forbidden_imports((src / name).read_text()) == []


def test_boundary_guard_negative_controls():
    assert forbidden_imports("from credentialgate.storage import connect")
    assert forbidden_imports("from .policy import authorize")
    assert forbidden_imports("import sqlite3")
