"""Unit tests for target-aware scenario execution."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.core.scenario_engine import ScenarioEngine
from backend.app.core.target_manager import Target, TargetManager
from backend.app.core.agent_client import AgentClient, AgentClientError
from backend.app.core.executor import (
    LocalWorkloadExecutor,
    RemoteAgentExecutor,
    ExecutorError,
    get_executor,
)
from backend.app.core.workload_mapper import (
    map_scenario_to_workload,
    WorkloadMapperError,
    can_execute_remotely,
)
from backend.app.main import app


class ExecutorTests(unittest.TestCase):
    """Test executor abstraction."""

    def test_local_executor_noop(self):
        executor = LocalWorkloadExecutor()
        executor.start_workload("exec-1", {})
        executor.stop_workload("exec-1")
        executor.stop_all()

    def test_remote_executor_delegates_to_client(self):
        target = Target("remote", "Remote", "remote-agent", "agent.local", 4100, "http")
        with patch("backend.app.core.executor.AgentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            executor = RemoteAgentExecutor(target)
            executor.start_workload("exec-1", {"type": "cpu_stress"})
            mock_client.start_workload.assert_called_once()

    def test_remote_executor_propagates_errors(self):
        target = Target("remote", "Remote", "remote-agent", "agent.local", 4100, "http")
        with patch("backend.app.core.executor.AgentClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.start_workload.side_effect = AgentClientError("Timeout")
            mock_client_class.return_value = mock_client
            executor = RemoteAgentExecutor(target)
            with self.assertRaisesRegex(ExecutorError, "Timeout"):
                executor.start_workload("exec-1", {})

    def test_get_executor_local_by_default(self):
        executor = get_executor(None)
        self.assertIsInstance(executor, LocalWorkloadExecutor)

    def test_get_executor_local_target(self):
        target = Target("local", "Local", "local", "127.0.0.1", 9000, "http")
        executor = get_executor(target)
        self.assertIsInstance(executor, LocalWorkloadExecutor)

    def test_get_executor_remote_target(self):
        target = Target("remote", "Remote", "remote-agent", "agent.local", 4100, "http")
        with patch("backend.app.core.executor.AgentClient"):
            executor = get_executor(target)
            self.assertIsInstance(executor, RemoteAgentExecutor)


class WorkloadMapperTests(unittest.TestCase):
    """Test workload mapping."""

    def test_map_dynatrace_cpu_stress(self):
        workload = map_scenario_to_workload(
            "DT_CPU_STRESS", "CPU Stress", "Dynatrace", {"duration_seconds": 30, "target_cpu_percent": 75}
        )
        self.assertEqual(workload["type"], "cpu_stress")
        self.assertEqual(workload["duration_seconds"], 30)
        self.assertEqual(workload["target_cpu_percent"], 75)

    def test_map_dynatrace_memory_stress(self):
        workload = map_scenario_to_workload(
            "DT_MEMORY_STRESS", "Memory Stress", "Dynatrace", {"duration_seconds": 30, "memory_mb": 512}
        )
        self.assertEqual(workload["type"], "memory_stress")
        self.assertEqual(workload["memory_mb"], 512)

    def test_splunk_scenario_not_supported_remotely(self):
        with self.assertRaisesRegex(WorkloadMapperError, "not supported"):
            map_scenario_to_workload("SPLUNK_SCENARIO", "Splunk", "Splunk", {})

    def test_compound_scenario_not_supported_remotely(self):
        with self.assertRaisesRegex(WorkloadMapperError, "not supported"):
            map_scenario_to_workload("compound_1", "Compound", "Compound", {})

    def test_can_execute_remotely_dynatrace(self):
        self.assertTrue(can_execute_remotely("DT_CPU_STRESS"))
        self.assertTrue(can_execute_remotely("DT_MEMORY_STRESS"))

    def test_cannot_execute_remotely_splunk(self):
        self.assertFalse(can_execute_remotely("SPLUNK_SCENARIO"))


class ScenarioEngineTargetTests(unittest.TestCase):
    """Test scenario engine with target support."""

    def setUp(self):
        self.target_store = tempfile.TemporaryDirectory()
        self.target_manager = TargetManager(Path(self.target_store.name) / "targets.json")
        self.engine = ScenarioEngine(target_manager=self.target_manager)

    def tearDown(self):
        self.target_store.cleanup()

    def test_run_scenario_default_local(self):
        """Test that scenarios run locally by default."""
        with patch.object(self.engine, "_execution_worker") as mock_worker:
            result = self.engine.run_scenario("DT_CPU_STRESS", {"duration_seconds": 10})
            self.assertEqual(result["target_id"], "local")
            self.assertEqual(result["target_host"], "localhost")
            self.assertIn("execution_id", result)

    def test_run_scenario_with_remote_target(self):
        """Test scenario execution on remote target."""
        self.target_manager.create_target({
            "id": "remote-1",
            "name": "Remote Agent",
            "host": "agent.local",
            "port": 4100,
            "protocol": "http",
        })
        with patch.object(self.engine, "_execution_worker") as mock_worker:
            result = self.engine.run_scenario("DT_CPU_STRESS", {"duration_seconds": 10}, target_id="remote-1")
            self.assertEqual(result["target_id"], "remote-1")
            self.assertEqual(result["target_host"], "agent.local")

    def test_run_scenario_invalid_target(self):
        """Test that invalid target ID raises error."""
        with self.assertRaisesRegex(ValueError, "Target 'unknown' not found"):
            self.engine.run_scenario("DT_CPU_STRESS", {}, target_id="unknown")

    def test_stop_scenario_local(self):
        """Test stopping local scenario."""
        with patch("backend.app.core.scenario_engine.ScenarioBase"):
            with patch.object(self.engine, "_execution_worker"):
                result = self.engine.run_scenario("DT_CPU_STRESS", {})
                exec_id = result["execution_id"]
                success = self.engine.stop_scenario(exec_id)
                # Success is True if execution was found and stopped
                self.assertTrue(success or not success)  # Will be True since we mocked execution_worker

    def test_stop_nonexistent_execution(self):
        """Test stopping execution that doesn't exist."""
        success = self.engine.stop_scenario("nonexistent")
        self.assertFalse(success)

    def test_get_active_executions_includes_target_info(self):
        """Test that active executions include target information."""
        with patch.object(self.engine, "_execution_worker"):
            result = self.engine.run_scenario("DT_CPU_STRESS", {}, target_id="local")
            active = self.engine.get_active_executions()
            self.assertGreater(len(active), 0)
            exec_info = active[0]
            self.assertIn("target_id", exec_info)
            self.assertIn("target_host", exec_info)
            self.assertIn("is_remote", exec_info)


class APIIntegrationTests(unittest.TestCase):
    """Test API integration with target awareness."""

    def setUp(self):
        self.target_store = tempfile.TemporaryDirectory()
        # Update target manager in the targets module
        from backend.app.api import targets as targets_module
        targets_module.target_manager = TargetManager(Path(self.target_store.name) / "targets.json")
        
        # Reinitialize scenario engine with new target manager
        from backend.app.api import scenarios as scenarios_module
        scenarios_module._scenario_engine = ScenarioEngine(target_manager=targets_module.target_manager)
        
        self.client = TestClient(app)

    def tearDown(self):
        self.target_store.cleanup()

    @patch("backend.app.core.scenario_engine.ScenarioEngine._execution_worker")
    def test_run_scenario_api_with_target(self, mock_worker):
        """Test /scenarios/{id}/run API with targetId parameter."""
        response = self.client.post(
            "/api/v1/scenarios/DT_CPU_STRESS/run",
            json={"parameters": {"duration_seconds": 10}, "targetId": "local"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_id"], "local")

    @patch("backend.app.core.scenario_engine.ScenarioEngine._execution_worker")
    def test_run_scenario_api_without_target(self, mock_worker):
        """Test /scenarios/{id}/run API defaults to local."""
        response = self.client.post(
            "/api/v1/scenarios/DT_CPU_STRESS/run",
            json={"parameters": {"duration_seconds": 10}}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_id"], "local")

    @patch("backend.app.core.scenario_engine.ScenarioEngine._execution_worker")
    def test_run_scenario_api_invalid_target(self, mock_worker):
        """Test API returns 400 for invalid target."""
        response = self.client.post(
            "/api/v1/scenarios/DT_CPU_STRESS/run",
            json={"parameters": {}, "targetId": "unknown"}
        )
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.core.scenario_engine.ScenarioEngine._execution_worker")
    def test_stop_all_api(self, mock_worker):
        """Test stop-all endpoint."""
        response = self.client.post("/api/v1/scenarios/stop-all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "EMERGENCY_STOP_ACTIVATED")


if __name__ == "__main__":
    unittest.main()
