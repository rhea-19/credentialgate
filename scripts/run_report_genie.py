"""Run the bundled synthetic Report Genie walkthrough from a single repository."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                str(ROOT / "integrations/report-genie/scripts/run_evidence_demo.py"),
                "--credentialgate",
                str(ROOT),
                *sys.argv[1:],
            ]
        )
    )
