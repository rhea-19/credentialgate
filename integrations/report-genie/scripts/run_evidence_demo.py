"""Launch the synthetic Report Genie + CredentialGate integration locally."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--credentialgate", type=Path, default=ROOT.parents[1]
    )
    parser.add_argument("--port", type=int, default=5002)
    parser.add_argument("--api-port", type=int, default=8011)
    args = parser.parse_args()
    cg = args.credentialgate.resolve()
    python = cg / ".venv/bin/python"
    data = cg / "var/report-genie-demo"
    if not python.is_file():
        raise SystemExit(
            "Create CredentialGate's .venv first; see docs/credential-integration.md"
        )
    if not (data / "credentials.db").exists():
        subprocess.run(
            [str(python), "-m", "credentialgate.bootstrap", "--data-dir", str(data)],
            check=True,
        )
    subprocess.run(
        [
            str(python),
            "-m",
            "credentialgate.bind_report",
            str(ROOT / "resources/credential-demo.pdf"),
            "--provider",
            "prov_demo_001",
            "--data-dir",
            str(data),
        ],
        check=True,
    )
    token = json.loads((data / "clients.json").read_text())["public"]
    api_url = f"http://127.0.0.1:{args.api_port}"
    api = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "credentialgate.service:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.api_port),
            "--no-access-log",
        ],
        env={**os.environ, "CREDENTIALGATE_DATA_DIR": str(data)},
        cwd=cg,
    )
    web = None
    try:
        for _ in range(50):
            if api.poll() is not None:
                raise RuntimeError(
                    "Credential service did not start; check whether the port is in use"
                )
            try:
                with urllib.request.urlopen(
                    api_url + "/healthz", timeout=1
                ) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Credential service startup timed out")
        env = {
            **os.environ,
            "REPORTGENIE_DEMO": "1",
            "REPORTGENIE_SECRET_KEY": secrets.token_hex(32),
            "REPORTGENIE_DATA_DIR": str(ROOT / "var/evidence-demo"),
            "PORT": str(args.port),
            "CREDENTIALGATE_MCP_PYTHON": str(python),
            "CREDENTIALGATE_API_URL": api_url,
            "CREDENTIALGATE_API_TOKEN": token,
        }
        print(
            f"\nReport Genie evidence demo: http://127.0.0.1:{args.port}\n", flush=True
        )
        web = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT, env=env)
        while web.poll() is None:
            if api.poll() is not None:
                raise RuntimeError("Credential service stopped")
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, api):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
