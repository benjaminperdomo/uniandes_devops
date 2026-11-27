"""Print a plan by default. --execute explicitly opens Locust (no auto-start)."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("scenario", choices=["normal", "stress", "errors"])
parser.add_argument("--host", required=True, help="Explicit target origin, no path or token")
parser.add_argument("--execute", action="store_true", help="Open local web UI; press Start to begin")
args = parser.parse_args()
host = urlsplit(args.host)
if (host.scheme not in {"http", "https"} or not host.hostname or host.username
        or host.password or host.path not in {"", "/"} or host.query or host.fragment):
    parser.error("--host must be an http(s) origin without credentials, path or query")
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
output = ROOT / "results" / f"{stamp}-{args.scenario}"
cmd = [sys.executable, "-m", "locust", "-f", str(ROOT / "locustfile.py"),
       "--host", args.host.rstrip("/"), "--web-host", "127.0.0.1",
       "--web-port", "8089", "--csv", str(output / "locust"),
       "--csv-full-history", "--html", str(output / "report.html"),
       "--stop-timeout", "20"]
print(json.dumps({"scenario": args.scenario, "host": args.host,
                  "output": str(output), "command": cmd}, indent=2))
if not args.execute:
    print("PLAN ONLY: no requests sent, no Locust process started.")
    sys.exit(0)
if not os.getenv("BLACKLIST_TOKEN", "").strip():
    print("Introduce el JWT en el campo protegido Blacklist token antes de pulsar Start.")
output.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, LOAD_SCENARIO=args.scenario, LOAD_EXECUTE="YES", LOAD_OUTPUT=str(output))
print("Open http://127.0.0.1:8089. Traffic starts only after Start. One run per launch.")
sys.exit(subprocess.call(cmd, env=env, cwd=ROOT))
