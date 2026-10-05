"""Host-only profile launcher. Loads demo client tokens, never credential records."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--profile",
    choices=["public", "institution", "reviewer", "other-institution"],
    default="public",
)
parser.add_argument("--clients", type=Path, default=Path("var/clients.json"))
parser.add_argument("--question")
parser.add_argument("--model")
args = parser.parse_args()
env = {**os.environ, "CREDENTIALGATE_API_TOKEN": json.loads(args.clients.read_text())[args.profile]}
command = [sys.executable, "-m", "credentialgate.client"]
if args.question:
    command.extend(["--question", args.question])
if args.model:
    command.extend(["--model", args.model])
raise SystemExit(subprocess.call(command, env=env))
