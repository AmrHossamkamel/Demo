from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class ExpectedOutcome(BaseModel):
    splunk_events: Optional[int] = 0
    dynatrace_signals: Optional[str] = "Normal Telemetry"
    expected_logs: Optional[str] = ""
    expected_metrics: Optional[str] = ""
    expected_anomaly: Optional[str] = ""
    investigation_story: Dict[str, Any] = {}

class ScenarioMetadata(BaseModel):
    id: str
    name: str
    category: str
    target_platform: str # "Splunk", "Dynatrace", "Compound"
    severity: str # "INFO", "WARNING", "CRITICAL"
    risk_level: str # "LOW", "MEDIUM", "HIGH"
    duration_seconds: int
    description: str
    expected_outcome: ExpectedOutcome

class ExecutionResult(BaseModel):
    execution_id: str
    scenario_id: str
    status: str # "COMPLETED", "FAILED", "STOPPED"
    events_generated: int
    duration_seconds: float
    error_message: Optional[str] = None
    telemetry_summary: Dict[str, Any] = {}

class ScenarioBase(ABC):
    """
    Abstract base class for all Splunk, Dynatrace, and Compound scenarios.
    Enforces a strict, consistent lifecycle interface.
    """
    def __init__(self, metadata: ScenarioMetadata):
        self.metadata = metadata
        self._is_running = False
        self._execution_id: Optional[str] = None

    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> bool:
        """Validates input parameters and environmental safety constraints."""
        pass

    @abstractmethod
    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        """Executes the telemetry/load generation sequence."""
        pass

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        """Returns current live status and metrics of the scenario execution."""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """Safely stops any active workers or sub-processes."""
        pass

    @abstractmethod
    def cleanup(self) -> bool:
        """Restores environment, releases memory/CPU load, resets fault injections."""
        pass

    def get_expected_results(self) -> ExpectedOutcome:
        """Returns the pre-defined expected telemetry outcome and Botify story."""
        return self.metadata.expected_outcome
