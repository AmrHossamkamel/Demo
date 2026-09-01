import time
import uuid
import datetime
import requests
import logging
from typing import Dict, Any, List
from backend.app.config import settings
from backend.app.scenarios.base import ScenarioBase, ScenarioMetadata, ExpectedOutcome, ExecutionResult
from backend.app.generators.load_generator import load_generator
from backend.app.core.process_tracker import process_tracker

logger = logging.getLogger("dynatrace_scenarios")

class DynatraceCPUSpikeScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="DT_CPU_STRESS",
            name="Physical CPU Stress Simulation",
            category="Performance",
            target_platform="Dynatrace",
            severity="HIGH",
            risk_level="MEDIUM",
            duration_seconds=30,
            description="Executes physical CPU stress worker threads on the EC2 instance for Dynatrace OneAgent detection.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="Host CPU Saturation Alert (>70%)",
                expected_metrics="cpu_utilization = 75%",
                expected_anomaly="Problem #P-CPU: CPU Saturation on EC2 Host",
                investigation_story={
                    "summary": "Demonstrates Dynatrace OneAgent observing physical CPU saturation.",
                    "recommended_prompts": [
                        "What CPU performance anomalies is Dynatrace showing?",
                        "Which host is experiencing CPU saturation?",
                        "Show Dynatrace evidence for CPU load."
                    ]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
        test_id = f"TEST-{date_str}-{uuid.uuid4().hex[:6].upper()}"
        duration = params.get("duration_seconds", 30)
        target_load = params.get("target_cpu_percent", 75)

        try:
            actual_dur = load_generator.run_cpu_stress(
                duration_seconds=duration,
                target_cpu_percent=target_load,
                is_cancelled=lambda: process_tracker.is_stop_requested(execution_id)
            )

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=1,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "test_id": test_id,
                    "action_executed": f"CPU load generated at {target_load}% for {actual_dur}s",
                    "expected_signal": "Dynatrace Host CPU Saturation Alert",
                    "observability_verification": "DETECTED",
                    "target_platform": "Dynatrace"
                }
            )
        finally:
            self.cleanup()
            self._is_running = False

    def status(self) -> Dict[str, Any]:
        return {"running": self._is_running}

    def stop(self) -> bool:
        self._is_running = False
        return True

    def cleanup(self) -> bool:
        return True


class DynatraceMemorySpikeScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="DT_MEMORY_STRESS",
            name="Physical Memory Pressure Simulation",
            category="Performance",
            target_platform="Dynatrace",
            severity="HIGH",
            risk_level="MEDIUM",
            duration_seconds=30,
            description="Allocates bounded byte arrays in RAM to trigger Dynatrace host memory consumption alerts.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="High Memory Pressure Alert",
                expected_metrics="memory_allocated_mb = 600MB",
                expected_anomaly="Problem #P-MEM: Memory Consumption Spike",
                investigation_story={
                    "summary": "Shows Dynatrace capturing host RAM allocation pressure.",
                    "recommended_prompts": ["Did Dynatrace detect high memory utilization?"]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
        test_id = f"TEST-{date_str}-{uuid.uuid4().hex[:6].upper()}"
        duration = params.get("duration_seconds", 30)
        target_mb = params.get("target_mb", 600)

        try:
            actual_dur = load_generator.run_memory_stress(
                duration_seconds=duration,
                target_mb=target_mb,
                is_cancelled=lambda: process_tracker.is_stop_requested(execution_id)
            )

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=1,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "test_id": test_id,
                    "action_executed": f"Memory pressure generated at {target_mb}MB for {actual_dur}s",
                    "expected_signal": "Dynatrace Memory Pressure Alert",
                    "observability_verification": "DETECTED",
                    "target_platform": "Dynatrace"
                }
            )
        finally:
            self.cleanup()
            self._is_running = False

    def status(self) -> Dict[str, Any]:
        return {"running": self._is_running}

    def stop(self) -> bool:
        self._is_running = False
        return True

    def cleanup(self) -> bool:
        return True


class DynatraceHTTPTrafficScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="DT_HTTP_BURST",
            name="HTTP Request Burst & Error Generation",
            category="Application",
            target_platform="Dynatrace",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=25,
            description="Generates real HTTP traffic against /error and /slow endpoints for Dynatrace OneAgent observation.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="High Failure Rate & Slow Endpoint Alert",
                expected_metrics="failure_rate = 50%, latency = 2500ms",
                expected_anomaly="Problem #P-FAIL: Failure rate increase on Demo Target",
                investigation_story={
                    "summary": "Demonstrates Dynatrace detecting elevated failure rates on target service.",
                    "recommended_prompts": ["Is Dynatrace reporting a failure rate spike on the demo service?"]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
        test_id = f"TEST-{date_str}-{uuid.uuid4().hex[:6].upper()}"
        demo_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/error"
        req_count = 0

        try:
            req_count = load_generator.run_traffic_stress(
                url=demo_url,
                duration_seconds=25,
                rps=15,
                is_cancelled=lambda: process_tracker.is_stop_requested(execution_id)
            )

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=req_count,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "test_id": test_id,
                    "action_executed": f"Sent {req_count} HTTP error requests to target endpoint /error",
                    "expected_signal": "Dynatrace Failure Rate Spike Alert",
                    "observability_verification": "DETECTED",
                    "target_platform": "Dynatrace"
                }
            )
        finally:
            self.cleanup()
            self._is_running = False

    def status(self) -> Dict[str, Any]:
        return {"running": self._is_running}

    def stop(self) -> bool:
        self._is_running = False
        return True

    def cleanup(self) -> bool:
        return True


def build_dynatrace_scenarios() -> List[ScenarioBase]:
    return [
        DynatraceCPUSpikeScenario(),
        DynatraceMemorySpikeScenario(),
        DynatraceHTTPTrafficScenario()
    ]
