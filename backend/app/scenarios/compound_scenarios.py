import time
import requests
import logging
from typing import Dict, Any, List
from backend.app.config import settings
from backend.app.scenarios.base import ScenarioBase, ScenarioMetadata, ExpectedOutcome, ExecutionResult
from backend.app.generators.splunk_generator import splunk_generator
from backend.app.generators.load_generator import load_generator
from backend.app.core.process_tracker import process_tracker

logger = logging.getLogger("compound_scenarios")

class PaymentServiceDegradationScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="compound-payment-degradation",
            name="Payment Service Degradation (Full Incident)",
            category="Compound Workflows",
            target_platform="Splunk & Dynatrace",
            severity="CRITICAL",
            risk_level="HIGH",
            duration_seconds=60,
            description="Orchestrates a multi-stage cascading outage: Traffic burst -> Latency degradation -> HTTP 500 errors -> App exceptions -> Physical CPU load -> Correlated Splunk & Dynatrace telemetry.",
            expected_outcome=ExpectedOutcome(
                splunk_events=85,
                dynatrace_signals="Problem #P-24091: Payment Service Degradation & CPU Saturation",
                expected_logs="DATABASE_CONNECTION_TIMEOUT, PaymentProcessorException, HTTP_500",
                expected_metrics="avg_response_time = 3200ms, failure_rate = 38%, cpu = 78%",
                expected_anomaly="Cascading multi-component incident on Payment Core",
                investigation_story={
                    "summary": "Primary demonstration scenario showcasing Botify correlating Dynatrace metrics with Splunk log root causes.",
                    "recommended_prompts": [
                        "What happened to the payment service?",
                        "Is there an active incident?",
                        "What changed in the last 10 minutes?",
                        "What are the main errors?",
                        "Which service is affected?",
                        "What is the likely root cause?",
                        "Show me evidence from Splunk.",
                        "Show me the Dynatrace evidence.",
                        "Are these two incidents related?"
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
        total_events = 0

        try:
            logger.info("Executing Compound Scenario: Payment Service Degradation")

            # Stage 1: Initial Traffic Spike & Warning Logs
            splunk_generator.send_event(splunk_generator.create_event(
                event_type="TRAFFIC_BURST_DETECTED",
                service="api-gateway",
                severity="INFO",
                message="Traffic burst detected on payment endpoints: +350 req/sec"
            ))
            total_events += 1

            # Stage 2: Inject Response Time Latency (2800ms)
            requests.post(fault_url, json={"latency_ms": 2800}, timeout=2)
            splunk_generator.send_event(splunk_generator.create_event(
                event_type="RESPONSE_TIME_WARNING",
                service="payment-service",
                severity="WARNING",
                response_time=2800,
                message="Payment processor latency threshold exceeded: 2800ms"
            ))
            total_events += 1
            time.sleep(2)

            # Stage 3: Inject HTTP 500 & DB Timeouts
            requests.post(fault_url, json={"latency_ms": 3200, "force_500_rate": 0.40, "force_db_timeout": True}, timeout=2)

            for i in range(25):
                if process_tracker.is_stop_requested(execution_id):
                    break
                splunk_generator.send_event(splunk_generator.create_event(
                    event_type="DATABASE_CONNECTION_TIMEOUT",
                    service="payment-service",
                    severity="CRITICAL",
                    status_code=504,
                    response_time=3200,
                    client_ip=f"10.0.3.{i+10}",
                    username=f"usr_{8000+i}",
                    message=f"DB_CONNECTION_TIMEOUT on /api/v1/payments: HikariPool connection exhausted after 3000ms. User usr_{8000+i}"
                ))
                total_events += 1

            # Stage 4: Trigger CPU Stress & Application Exceptions concurrently
            splunk_generator.send_event(splunk_generator.create_event(
                event_type="APPLICATION_EXCEPTION",
                service="payment-service",
                severity="ERROR",
                status_code=500,
                message="Unhandled NullPointerException in PaymentCoreThread.java:142"
            ))
            total_events += 1

            load_generator.run_cpu_stress(
                duration_seconds=15,
                target_cpu_percent=78,
                is_cancelled=lambda: process_tracker.is_stop_requested(execution_id)
            )

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=total_events,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "compound_orchestration": "Full Payment Service Cascading Outage",
                    "total_telemetry_events": total_events,
                    "target_platforms": ["Splunk", "Dynatrace"]
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


class AuthenticationAttackScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="compound-auth-attack",
            name="Authentication Attack & Credential Stuffing",
            category="Compound Workflows",
            target_platform="Splunk & Dynatrace",
            severity="CRITICAL",
            risk_level="MEDIUM",
            duration_seconds=40,
            description="Simulates a multi-vector auth attack: Rapid failed logins -> Suspicious IP distribution -> Successful account takeover -> High volume security log surge.",
            expected_outcome=ExpectedOutcome(
                splunk_events=60,
                dynatrace_signals="Authentication volume anomaly alert",
                expected_logs="FAILED_LOGIN_ATTEMPT, SUSPICIOUS_LOGIN_SUCCESS, ACCOUNT_TAKEOVER_ALERT",
                investigation_story={
                    "summary": "Demonstrates Botify investigating multi-user credential stuffing and security compromise.",
                    "recommended_prompts": [
                        "Are there any security threats detected?",
                        "Identify the suspicious IPs involved in the authentication attack.",
                        "Was any user account compromised?"
                    ]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        total_events = 0
        suspicious_ips = ["185.220.101.5", "185.220.101.6", "45.154.255.85"]

        try:
            # 1. Surge of failed logins
            for i in range(40):
                if process_tracker.is_stop_requested(execution_id):
                    break
                ip = random.choice(suspicious_ips)
                user = f"vip_user_{i % 5}"
                splunk_generator.send_event(splunk_generator.create_event(
                    event_type="FAILED_LOGIN_ATTEMPT",
                    service="auth-service",
                    severity="WARNING",
                    client_ip=ip,
                    username=user,
                    http_method="POST",
                    endpoint="/api/v1/auth/login",
                    status_code=401,
                    message=f"Credential check failed for user {user} from suspicious proxy IP {ip}"
                ))
                total_events += 1
                time.sleep(0.05)

            # 2. Breach login success
            splunk_generator.send_event(splunk_generator.create_event(
                event_type="ACCOUNT_TAKEOVER_ALERT",
                service="auth-service",
                severity="CRITICAL",
                client_ip="185.220.101.5",
                username="vip_user_2",
                http_method="POST",
                endpoint="/api/v1/auth/login",
                status_code=200,
                message="SUCCESSFUL LOGIN AFTER 38 FAILURES: Account vip_user_2 compromised from proxy IP 185.220.101.5"
            ))
            total_events += 1

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=total_events,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={"security_attack_events": total_events}
            )
        finally:
            self._is_running = False

    def status(self) -> Dict[str, Any]:
        return {"running": self._is_running}

    def stop(self) -> bool:
        self._is_running = False
        return True

    def cleanup(self) -> bool:
        return True


class DatabaseDependencyFailureScenario(ScenarioBase):
    def __init__(self):
        super().__init__(ScenarioMetadata(
            id="compound-db-dependency-failure",
            name="Database Dependency Failure & Gateway Timeouts",
            category="Compound Workflows",
            target_platform="Splunk & Dynatrace",
            severity="HIGH",
            risk_level="MEDIUM",
            duration_seconds=45,
            description="Simulates DB latency leading to cascading API timeouts and service unavailability.",
            expected_outcome=ExpectedOutcome(
                splunk_events=50,
                dynatrace_signals="Problem #P-DB: Database Dependency Timeout",
                expected_logs="DATABASE_LATENCY_WARNING, API_TIMEOUT_ERROR, 504_GATEWAY_TIMEOUT",
                investigation_story={
                    "summary": "Demonstrates Botify linking API gateway timeouts directly to database pool latency.",
                    "recommended_prompts": [
                        "Why are API requests timing out?",
                        "Is the database healthy?",
                        "Show correlation between DB latency and API error rates."
                    ]
                }
            )
        ))

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._is_running = True
        start_time = time.time()
        fault_url = f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/demo/fault-injection"
        total_events = 0

        try:
            requests.post(fault_url, json={"force_db_timeout": True}, timeout=2)

            for i in range(30):
                if process_tracker.is_stop_requested(execution_id):
                    break
                splunk_generator.send_event(splunk_generator.create_event(
                    event_type="DATABASE_LATENCY_WARNING",
                    service="account-service",
                    severity="ERROR",
                    status_code=504,
                    response_time=5000,
                    message="DB Dependency timeout: Query on table 'account_balances' exceeded 5000ms limit."
                ))
                total_events += 1
                time.sleep(0.1)

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=total_events,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={"db_failure_events": total_events}
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


def build_compound_scenarios() -> List[ScenarioBase]:
    return [
        PaymentServiceDegradationScenario(),
        AuthenticationAttackScenario(),
        DatabaseDependencyFailureScenario()
    ]
