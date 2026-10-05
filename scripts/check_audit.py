import argparse
import json
from pathlib import Path

from credentialgate.storage import check_audit

parser = argparse.ArgumentParser(description="Check a local audit chain as the service operator.")
parser.add_argument("--database", type=Path, default=Path("var/credentials.db"))
args = parser.parse_args()
result = check_audit(args.database)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["valid"] else 2)
