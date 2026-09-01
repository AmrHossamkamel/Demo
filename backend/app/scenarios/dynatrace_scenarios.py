import time
import requests
import logging
from typing import Dict, Any, List
from backend.app.config import settings
from backend.app.scenarios.base import ScenarioBase, ScenarioMetadata, ExpectedOutcome, ExecutionResult
from backend.app.generators.load_generator import load_generator
from backend.app.generators.splunk_generator import splunk_generator
from backend.app.core.process_tracker import process_tracker

logger = logging.getLogger("dynatrace_scenarios")

class DynatraceCPUSpikeScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="dt-perf-cpu-spike",
            name="Physical CPU Spike Simulation",
            category="Performance",
            target_platform="Dynatrace",
            severity="HIGH",
            risk_level="MEDIUM",
            duration_seconds=30,
            description="Executes physical CPU stress worker threads on the EC2 instance, causing Dynatrace OneAgent to record host CPU saturation.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="Host CPU Saturation Alert (>70%)",
                expected_metrics="cpu_utilization = 75%",
                expected_anomaly="Problem #P-CPU: CPU Saturation on EC2 Host",
                investigation_story={
                    "summary": "Demonstrates Dynatrace detecting real CPU load saturation on the EC2 node.",
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
        duration = params.get("duration_seconds", 30)
        target_load = params.get("target_cpu_percent", 75)

        try:
            # Emit correlated log to Splunk as well for Dynatrace/Splunk cross-correlation
            splunk_generator.send_event(splunk_generator.create_event(
                event_type="HOST_CPU_SPIKE_STARTED",
                service="system-kernel",
                severity="WARNING",
                message=f"CPU load stress initiated: target={target_load}%"
            ))

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
                    "dynatrace_signal": "Host CPU Saturation",
                    "target_cpu_percent": target_load,
                    "actual_duration": actual_dur
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
            id="dt-perf-memory-spike",
            name="Physical Memory Stress Simulation",
            category="Performance",
            target_platform="Dynatrace",
            severity="HIGH",
            risk_level="MEDIUM",
            duration_seconds=30,
            description="Allocates bounded byte arrays in RAM for a controlled duration to trigger Dynatrace host memory consumption alerts.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="High Memory Consumption Alert",
                expected_metrics="memory_allocated_mb = 600MB",
                expected_anomaly="Problem #P-MEM: Memory Consumption Spike",
                investigation_story={
                    "summary": "Shows Dynatrace capturing host RAM allocation spikes.",
                    "recommended_prompts": ["Did Dynatrace detect high memory utilization?"]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
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
                    "dynatrace_signal": "Host Memory Stress",
                    "target_mb": target_mb
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

class DynatraceHTTP500SpikeScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="dt-app-http500-spike",
            name="Application HTTP 500 Error Surge",
            category="Application",
            target_platform="Dynatrace",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=25,
            description="Injects a 70% error rate into the Demo Banking Microservice and floods requests to trigger Dynatrace Service Failure Rate alerts.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="High Failure Rate Alert (>50%)",
                expected_metrics="failure_rate = 70%",
                expected_anomaly="Problem #P-FAIL: Failure rate increase on Demo Banking Service",
                investigation_story={
                    "summary": "Demonstrates Dynatrace detecting elevated application failure rates.",
                    "recommended_prompts": [
                        "Is Dynatrace reporting a failure rate spike on the banking service?",
                        "What is the error rate percentage?"
                    ]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        demo_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/payments/process"
        fault_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/demo/fault-injection"

        try:
            # 1. Inject Fault into Demo Banking App
            requests.post(fault_url, json={"force_500_rate": 0.70}, timeout=2)

            # 2. Run traffic stress
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
                    "dynatrace_signal": "Service Failure Rate Spike",
                    "failure_rate": "70%",
                    "requests_sent": req_count
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
        reset_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/demo/reset-faults"
        try:
            requests.post(reset_url, timeout=2)
        except Exception:
            pass
        return True

class DynatraceLatencySpikeScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="dt-perf-latency-spike",
            name="Endpoint Response Latency Degradation",
            category="Performance",
            target_platform="Dynatrace",
            severity="WARNING",
            risk_level="LOW",
            duration_seconds=30,
            description="Injects artificial 2500ms response delay into the Demo Banking Service endpoints, causing Dynatrace Response Time Degradation alerts.",
            expected_outcome=ExpectedOutcome(
                dynatrace_signals="Service Response Time Degradation Alert (>2000ms)",
                expected_metrics="avg_response_time = 2500ms",
                expected_anomaly="Problem #P-SLOW: Response time degradation on /api/v1/payments",
                investigation_story={
                    "summary": "Demonstrates Dynatrace identifying endpoint latency degradation.",
                    "recommended_prompts": ["Which endpoint is experiencing response latency?"]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        demo_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/payments/process"
        fault_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/demo/fault-injection"

        try:
            requests.post(fault_url, json={"latency_ms": 2500}, timeout=2)
            req_count = load_generator.run_traffic_stress(
                url=demo_url,
                duration_seconds=25,
                rps=5,
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
                    "dynatrace_signal": "Response Time Degradation",
                    "latency_ms": 2500
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
        reset_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/demo/reset-faults"
        try:
            requests.post(reset_url, timeout=2)
        except Exception:
            pass
        return True

def build_dynatrace_scenarios() -> List[ScenarioBase]:
    return [
        DynatraceCPUSpikeScenario(),
        DynatraceMemorySpikeScenario(),
        DynatraceHTTP500SpikeScenario(),
        DynatraceLatencySpikeScenario()
    ]
