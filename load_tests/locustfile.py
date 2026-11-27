"""Blacklist API: no network activity on import; traffic starts only on Start."""
import json
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

from locust import HttpUser, LoadTestShape, between, events, task
from locust.exception import StopUser

# Cumulative seconds, concurrent users, spawn rate (users/second).
PROFILES = {
    "normal": [(60, 2, 1), (420, 5, 1), (480, 2, 1)],
    "stress": [(60, 5, 1), (180, 10, 2), (300, 25, 3),
               (420, 50, 5), (780, 100, 5), (900, 5, 5)],
    "errors": [(60, 5, 1), (420, 10, 2), (540, 5, 2)],
}
SCENARIO = os.getenv("LOAD_SCENARIO", "normal")
if SCENARIO not in PROFILES:
    raise ValueError("LOAD_SCENARIO must be normal, stress or errors")


def stage_at(seconds, scenario=SCENARIO):
    for end, users, rate in PROFILES[scenario]:
        if seconds < end:
            return users, rate
    return None


def valid_host(host):
    url = urlsplit(host or "")
    return (url.scheme in {"http", "https"} and bool(url.hostname)
            and not url.username and not url.password
            and url.path in {"", "/"} and not url.query and not url.fragment)


class ScenarioShape(LoadTestShape):
    def tick(self):
        return stage_at(self.get_run_time())


@events.init_command_line_parser.add_listener
def token_input(parser):
    parser.add_argument("--blacklist-token", default="", is_secret=True,
                        help="JWT del ambiente (sin Bearer). No se guarda en reportes.")


@events.test_start.add_listener
def validate_start(environment, **kwargs):
    """Reject accidental execution and missing configuration before users spawn."""
    options = getattr(environment, "parsed_options", None)
    token = (getattr(options, "blacklist_token", "")
             or os.getenv("BLACKLIST_TOKEN", "")).strip()
    if (os.getenv("LOAD_EXECUTE") != "YES" or not token
            or token.lower().startswith("bearer ") or not valid_host(environment.host)):
        environment.process_exit_code = 2
        environment.runner.quit()
        raise RuntimeError("Set LOAD_EXECUTE=YES, BLACKLIST_TOKEN (JWT only), and a valid --host.")
    # This harness deliberately supports one local process so metadata and limits
    # cannot be accidentally multiplied by distributed workers.
    if environment.parsed_options and (
        getattr(environment.parsed_options, "master", False)
        or getattr(environment.parsed_options, "worker", False)
        or getattr(environment.parsed_options, "processes", None)
    ):
        environment.runner.quit()
        raise RuntimeError("Use a single Locust process, without master/worker/processes.")
    environment.load_token = token
    environment.load_run = {
        "scenario": SCENARIO,
        "run_id": uuid.uuid4().hex,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "host": environment.host,
        "stages": PROFILES[SCENARIO],
        "expected_failures": 0,
        "unexpected_failures": 0,
    }
    logging.info("Starting %s profile (max %s users)", SCENARIO,
                 max(s[1] for s in PROFILES[SCENARIO]))


@events.test_stop.add_listener
def save_run(environment, **kwargs):
    if not hasattr(environment, "load_run"):
        return
    environment.load_run["ended_utc"] = datetime.now(timezone.utc).isoformat()
    folder = Path(os.getenv("LOAD_OUTPUT", "results"))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "run.json").write_text(
        json.dumps(environment.load_run, indent=2), encoding="utf-8")


class BlacklistUser(HttpUser):
    wait_time = between(1, 3)

    def checked(self, method, path, name, expected, predicate=None, intentional=False, **kwargs):
        # Names are fixed: email identifiers do not create a Locust row per user.
        with self.client.request(method, path, name=name, timeout=(5, 15),
                                 allow_redirects=False, catch_response=True, **kwargs) as response:
            matched = response.status_code == expected
            if matched and predicate:
                try:
                    matched = bool(predicate(response.json()))
                except (ValueError, TypeError, KeyError, AttributeError):
                    matched = False
            if not matched:
                self.environment.load_run["unexpected_failures"] += 1
                response.failure(f"Unexpected HTTP/body; expected {expected}, got {response.status_code}")
            elif intentional:
                self.environment.load_run["expected_failures"] += 1
                response.failure(f"INTENTIONAL_HTTP_{expected}")
            else:
                response.success()
            # Authentication failure on a normal request invalidates the run.
            if not intentional and response.status_code in (401, 422):
                self.environment.process_exit_code = 2
                self.environment.runner.quit()
                raise StopUser()
            return matched

    def on_start(self):
        self.client.headers.update({
            "Authorization": "Bearer " + self.environment.load_token,
            "User-Agent": "blacklist-locust/entrega4",
            "X-Load-Test-Run": self.environment.load_run["run_id"],
        })
        # One synthetic DB row per spawned user, reused throughout that user's life.
        self.email = f"load-{uuid.uuid4().hex}@example.com"
        self.reason = "Synthetic Locust entrega4 " + self.environment.load_run["run_id"]
        ok = self.checked("POST", "/blacklists", "SETUP POST /blacklists", 201,
                          lambda body: body.get("email") == self.email,
                          json={"email": self.email, "app_uuid": str(uuid.uuid4()),
                                "blocked_reason": self.reason})
        if not ok:
            self.environment.process_exit_code = 2
            self.environment.runner.quit()
            raise StopUser()

    @task
    def traffic(self):
        # errors has a one-minute baseline and two-minute recovery window.
        elapsed = self.environment.shape_class.get_run_time()
        errors_active = SCENARIO == "errors" and 60 <= elapsed < 420
        choice = random.random()
        if errors_active and choice < 0.30:
            self.checked("POST", "/blacklists", "ERROR POST /blacklists [400]", 400,
                         lambda b: b.get("message") == "Validation error",
                         intentional=True, json={"email": "invalid", "app_uuid": "invalid"})
        elif errors_active and choice < 0.50:
            self.checked("GET", "/blacklists/unauthorized@example.com",
                         "ERROR GET /blacklists/:email [401]", 401,
                         lambda b: b.get("message") == "Missing authorization token",
                         intentional=True, headers={"Authorization": None})
        elif choice < 0.90:
            self.checked("GET", "/blacklists/" + quote(self.email, safe=""),
                         "GET /blacklists/:email [DB]", 200,
                         lambda b: b.get("is_blacklisted") is True
                         and b.get("blocked_reason") == self.reason)
        else:
            self.checked("GET", "/health", "GET /health", 200,
                         lambda b: b.get("status") == "ok")
