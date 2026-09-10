"""Clean executor abstraction for local and remote workload execution."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging

from backend.app.core.agent_client import AgentClient, AgentClientError
from backend.app.core.target_manager import Target

logger = logging.getLogger("executor")


class ExecutorError(Exception):
    """Base error for executor operations."""


class WorkloadExecutor(ABC):
    """Abstract base class for workload execution."""

    @abstractmethod
    def start_workload(self, execution_id: str, workload: Dict[str, Any]) -> None:
        """Start a workload. Raises ExecutorError on failure."""
        pass

    @abstractmethod
    def stop_workload(self, execution_id: str) -> None:
        """Stop a specific workload. Raises ExecutorError on failure."""
        pass

    @abstractmethod
    def stop_all(self) -> None:
        """Stop all workloads. Raises ExecutorError on failure."""
        pass


class LocalWorkloadExecutor(WorkloadExecutor):
    """Executor for local workload execution (default behavior)."""

    def start_workload(self, execution_id: str, workload: Dict[str, Any]) -> None:
        """Local execution is handled by scenario's execute() method."""
        pass

    def stop_workload(self, execution_id: str) -> None:
        """Local execution is stopped by scenario's stop() method."""
        pass

    def stop_all(self) -> None:
        """Local stop-all is handled by scenario_engine.stop_all()."""
        pass


class RemoteAgentExecutor(WorkloadExecutor):
    """Executor for remote agent workload execution."""

    def __init__(self, target: Target) -> None:
        self.target = target
        self.client = AgentClient(target)

    def start_workload(self, execution_id: str, workload: Dict[str, Any]) -> None:
        """Start a workload on the remote agent."""
        try:
            self.client.start_workload(execution_id, workload)
        except AgentClientError as e:
            raise ExecutorError(str(e))

    def stop_workload(self, execution_id: str) -> None:
        """Stop a specific workload on the remote agent."""
        try:
            self.client.stop_workload(execution_id)
        except AgentClientError as e:
            raise ExecutorError(str(e))

    def stop_all(self) -> None:
        """Stop all workloads on the remote agent."""
        try:
            self.client.stop_all()
        except AgentClientError as e:
            raise ExecutorError(str(e))


def get_executor(target: Optional[Target]) -> WorkloadExecutor:
    """Get the appropriate executor for a target."""
    if target is None or target.type == "local":
        return LocalWorkloadExecutor()
    # Accept any remote target type (remote-agent, ec2-agent, agent — already canonicalized
    # by TargetManager to 'remote-agent', but keep this branch broad for safety).
    return RemoteAgentExecutor(target)
