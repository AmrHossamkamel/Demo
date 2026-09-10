import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.app.api import targets
from backend.app.core.agent_client import AgentClient, AgentClientError
from backend.app.core.target_manager import Target, TargetError, TargetManager
from backend.app.main import app


class TargetManagerTests(unittest.TestCase):
    def test_local_target_survives_persistence_and_cannot_be_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "targets.json"
            manager = TargetManager(path)
            manager.create_target({
                "id": "remote-1", "name": "Remote Agent", "host": "Example.COM.",
                "port": 4100, "protocol": "HTTPS",
            })
            restored = TargetManager(path)
            self.assertEqual([target.id for target in restored.list_targets()], ["local", "remote-1"])
            with self.assertRaises(TargetError):
                restored.remove_target("local")

    def test_invalid_target_is_rejected(self):
        manager = TargetManager(Path(tempfile.mkdtemp()) / "targets.json")
        with self.assertRaises(TargetError):
            manager.create_target({
                "id": "bad id", "name": "Remote", "host": "host/path",
                "port": 4100, "protocol": "http",
            })


class AgentClientTests(unittest.TestCase):
    def setUp(self):
        self.target = Target("remote", "Remote", "remote-agent", "agent.example", 4100, "https")

    def test_request_uses_bearer_header_without_exposing_token(self):
        response = Mock(status_code=200)
        response.json.return_value = {"status": "ok"}
        with patch("backend.app.core.agent_client.settings.BOTIFY_AGENT_TOKEN", "secret-token"), \
             patch("backend.app.core.agent_client.requests.request", return_value=response) as request:
            self.assertEqual(AgentClient(self.target).health(), {"status": "ok"})
        self.assertEqual(request.call_args.kwargs["headers"], {"Authorization": "Bearer secret-token"})

    def test_timeout_becomes_safe_domain_error(self):
        import requests
        with patch("backend.app.core.agent_client.requests.request", side_effect=requests.Timeout):
            with self.assertRaisesRegex(AgentClientError, "timed out"):
                AgentClient(self.target).health()


class TargetRouterTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        targets.target_manager = TargetManager(Path(self.directory.name) / "targets.json")
        self.client = TestClient(app)

    def tearDown(self):
        self.directory.cleanup()

    def test_list_create_delete_and_local_test(self):
        self.assertEqual(self.client.get("/api/v1/targets").status_code, 200)
        created = self.client.post("/api/v1/targets", json={
            "id": "remote", "name": "Remote", "host": "localhost",
            "port": 4100, "protocol": "http",
        })
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post("/api/v1/targets/local/test").status_code, 200)
        self.assertEqual(self.client.delete("/api/v1/targets/local").status_code, 400)
        self.assertEqual(self.client.delete("/api/v1/targets/remote").status_code, 200)

    def test_remote_test_failure_is_safe(self):
        self.client.post("/api/v1/targets", json={
            "id": "remote", "name": "Remote", "host": "localhost",
            "port": 4100, "protocol": "http",
        })
        with patch("backend.app.api.targets.AgentClient.health", side_effect=AgentClientError("timed out")):
            response = self.client.post("/api/v1/targets/remote/test")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "timed out")


if __name__ == "__main__":
    unittest.main()
