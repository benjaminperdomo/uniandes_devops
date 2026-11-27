"""Offline checks only. No Locust runner is started and HTTP is mocked."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from locust.env import Environment
from locust.exception import StopUser
from locustfile import BlacklistUser, PROFILES, stage_at, valid_host, validate_start


class OfflineChecks(unittest.TestCase):
    def test_stage_boundaries_and_stop(self):
        for scenario, stages in PROFILES.items():
            previous = 0
            for end, count, rate in stages:
                self.assertEqual(stage_at(previous, scenario), (count, rate))
                self.assertEqual(stage_at(end - 0.01, scenario), (count, rate))
                previous = end
            self.assertIsNone(stage_at(previous, scenario))

    def test_host_validation(self):
        self.assertTrue(valid_host("https://example.com"))
        for host in ["", "file:///tmp/a", "https://u:p@example.com", "https://example.com/token", "https://example.com?token=x"]:
            self.assertFalse(valid_host(host))

    def test_start_requires_explicit_execution(self):
        env = SimpleNamespace(host="https://example.com", runner=MagicMock())
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            validate_start(env)
        env.runner.quit.assert_called_once()

    def make_user(self, status, body):
        env = Environment(host="https://example.com")
        env.load_run = {"unexpected_failures": 0, "expected_failures": 0}
        env.runner = MagicMock()
        with patch.object(BlacklistUser, "host", "https://example.com"):
            user = BlacklistUser(env)
        user.client = MagicMock()
        response = MagicMock(status_code=status)
        response.json.return_value = body
        user.client.request.return_value.__enter__.return_value = response
        return user, response

    def test_expected_errors_remain_visible_as_failures(self):
        user, response = self.make_user(400, {})
        self.assertTrue(user.checked("POST", "/blacklists", "error", 400, intentional=True))
        response.failure.assert_called_once_with("INTENTIONAL_HTTP_400")
        self.assertEqual(user.environment.load_run["expected_failures"], 1)

    def test_wrong_body_is_failure(self):
        user, response = self.make_user(200, {"is_blacklisted": False})
        self.assertFalse(user.checked("GET", "/blacklists/x", "DB", 200,
                                      lambda b: b["is_blacklisted"] is True))
        response.failure.assert_called_once()

    def test_auth_failure_stops_run(self):
        user, response = self.make_user(401, {})
        with self.assertRaises(StopUser):
            user.checked("GET", "/blacklists/x", "DB", 200)
        user.environment.runner.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
