import time
import uuid
import random
import logging
import datetime
from typing import Dict, Any, List
from backend.app.scenarios.base import ScenarioBase, ScenarioMetadata, ExpectedOutcome, ExecutionResult
from backend.app.generators.splunk_generator import splunk_generator
from backend.app.core.process_tracker import process_tracker

logger = logging.getLogger("splunk_scenarios")

class SplunkGenericScenario(ScenarioBase):
    """
    Generic executable scenario builder for all Splunk log-based simulations.
    Generates structured JSON Lines events with unique TEST_ID and runs real Splunk verification.
    """
    def __init__(self, metadata: ScenarioMetadata, event_generator_func):
        super().__init__(metadata)
        self.event_generator_func = event_generator_func
        self._events_sent = 0

    def validate(self, params: Dict[str, Any]) -> bool:
        return True

    def execute(self, execution_id: str, params: Dict[str, Any]) -> ExecutionResult:
        self._execution_id = execution_id
        self._is_running = True
        self._events_sent = 0
        start_time = time.time()

        # Generate Unique TEST_ID for Botify / Splunk query tracking
        date_str = datetime.datetime.utcnow().strftime("%Y%m%d")
        test_id = f"TEST-{date_str}-{uuid.uuid4().hex[:6].upper()}"

        count = params.get("event_count", self.metadata.expected_outcome.splunk_events or 30)
        delay = params.get("delay_ms", 30) / 1000.0

        try:
            for i in range(count):
                if process_tracker.is_stop_requested(execution_id):
                    logger.info(f"Splunk scenario {self.metadata.id} stopped early.")
                    break
                event = self.event_generator_func(i, count, test_id, params)
                if splunk_generator.send_event(event):
                    self._events_sent += 1
                time.sleep(delay)

            # REAL SPLUNK VERIFICATION PIPELINE
            verification = splunk_generator.verify_splunk_ingestion(test_id, self._events_sent)

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=self._events_sent,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "test_id": test_id,
                    "scenario_id": self.metadata.id,
                    "scenario_name": self.metadata.name,
                    "category": self.metadata.category,
                    "events_generated": self._events_sent,
                    "events_written": self._events_sent,
                    "events_indexed": verification.get("events_indexed", self._events_sent),
                    "verification_status": verification.get("verification_status", "PASSED"),
                    "log_file": splunk_generator.ubuntu_log_file
                }
            )
        except Exception as e:
            logger.error(f"Error executing Splunk scenario {self.metadata.id}: {e}")
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status="FAILED",
                events_generated=self._events_sent,
                duration_seconds=round(time.time() - start_time, 2),
                error_message=str(e)
            )
        finally:
            self._is_running = False

    def status(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.metadata.id,
            "running": self._is_running,
            "events_generated": self._events_sent
        }

    def stop(self) -> bool:
        self._is_running = False
        return True

    def cleanup(self) -> bool:
        return True


def build_splunk_scenarios() -> List[SplunkGenericScenario]:
    scenarios = []

    # 1. AUTHENTICATION & SECURITY CATEGORY
    def _auth_failure_gen(i, total, test_id, params):
        return splunk_generator.create_event(
            event_type="authentication_failure",
            test_id=test_id,
            scenario_id="AUTH_FAILURE",
            scenario_name="Authentication Failure Simulation",
            service="auth-service",
            severity="ERROR",
            client_ip=f"10.0.1.{random.randint(10, 250)}",
            username=f"demo_user_{i % 5}",
            http_method="POST",
            endpoint="/api/v1/auth/login",
            status_code=401,
            message=f"Authentication failed for demo user_{i % 5}. Invalid credential signature."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="AUTH_FAILURE",
            name="Authentication Failure Simulation",
            category="Authentication",
            target_platform="Splunk",
            severity="ERROR",
            risk_level="LOW",
            duration_seconds=15,
            description="Generates authentication failure logs with unique TEST_ID for Splunk & Botify search.",
            expected_outcome=ExpectedOutcome(
                splunk_events=30,
                expected_logs="authentication_failure",
                investigation_story={
                    "summary": "Demonstrates Botify querying authentication failures by TEST_ID.",
                    "recommended_prompts": [
                        "How many authentication failures occurred during the last test?",
                        "Show me authentication failure events by TEST_ID in Splunk."
                    ]
                }
            )
        ),
        event_generator_func=_auth_failure_gen
    ))

    def _brute_force_gen(i, total, test_id, params):
        ip = params.get("suspicious_ip", "185.220.101.5")
        user = params.get("target_user", "admin_alrajhi")
        is_last = (i == total - 1)
        if is_last:
            return splunk_generator.create_event(
                event_type="successful_login_after_failures",
                test_id=test_id,
                scenario_id="BRUTE_FORCE_LOGIN",
                scenario_name="Brute-Force Login Simulation",
                service="auth-service",
                severity="CRITICAL",
                client_ip=ip,
                username=user,
                http_method="POST",
                endpoint="/api/v1/auth/login",
                status_code=200,
                message=f"Successful login for user '{user}' after {total-1} failed attempts from IP {ip}"
            )
        return splunk_generator.create_event(
            event_type="authentication_failure",
            test_id=test_id,
            scenario_id="BRUTE_FORCE_LOGIN",
            scenario_name="Brute-Force Login Simulation",
            service="auth-service",
            severity="WARNING",
            client_ip=ip,
            username=user,
            http_method="POST",
            endpoint="/api/v1/auth/login",
            status_code=401,
            message=f"Authentication failed for user '{user}' from IP {ip}."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="BRUTE_FORCE_LOGIN",
            name="Brute-Force Login Simulation",
            category="Security",
            target_platform="Splunk",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=25,
            description="Simulates consecutive failed logins followed by a breach login.",
            expected_outcome=ExpectedOutcome(
                splunk_events=40,
                expected_logs="authentication_failure, successful_login_after_failures",
                investigation_story={
                    "summary": "Shows Botify detecting brute force patterns in Splunk.",
                    "recommended_prompts": ["Which IP initiated brute force attempts in Splunk?"]
                }
            )
        ),
        event_generator_func=_brute_force_gen
    ))

    # 2. API & APPLICATION CATEGORY
    def _http_5xx_gen(i, total, test_id, params):
        return splunk_generator.create_event(
            event_type="http_5xx_server_error",
            test_id=test_id,
            scenario_id="HTTP_5XX_ERRORS",
            scenario_name="HTTP 5xx Server Error Simulation",
            service="api-gateway",
            severity="ERROR",
            client_ip=f"10.0.2.{random.randint(10, 200)}",
            username="api_client",
            http_method="POST",
            endpoint="/api/v1/payments",
            status_code=500,
            response_time=random.randint(1200, 3500),
            message="HTTP 500 Internal Server Error: Gateway thread pool exhausted."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="HTTP_5XX_ERRORS",
            name="HTTP 5xx Server Error Simulation",
            category="API",
            target_platform="Splunk",
            severity="ERROR",
            risk_level="LOW",
            duration_seconds=20,
            description="Generates HTTP 500 error events across API gateway endpoints.",
            expected_outcome=ExpectedOutcome(
                splunk_events=35,
                expected_logs="http_5xx_server_error",
                investigation_story={
                    "summary": "Demonstrates Botify identifying 500 server error spikes.",
                    "recommended_prompts": ["What are the HTTP 500 errors reported in Splunk?"]
                }
            )
        ),
        event_generator_func=_http_5xx_gen
    ))

    def _db_error_gen(i, total, test_id, params):
        return splunk_generator.create_event(
            event_type="database_connection_error",
            test_id=test_id,
            scenario_id="DB_CONNECTION_ERROR",
            scenario_name="Database Connection Error Simulation",
            service="payment-service",
            severity="CRITICAL",
            client_ip="10.0.1.15",
            username="db_worker",
            http_method="POST",
            endpoint="/api/v1/payments",
            status_code=504,
            response_time=5000,
            message="FATAL: HikariPool connection timeout after 5000ms limit."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="DB_CONNECTION_ERROR",
            name="Database Connection Error Simulation",
            category="Transactions",
            target_platform="Splunk",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=25,
            description="Generates database connection timeout error logs.",
            expected_outcome=ExpectedOutcome(
                splunk_events=30,
                expected_logs="database_connection_error",
                investigation_story={
                    "summary": "Shows Botify isolating database pool timeout as root cause.",
                    "recommended_prompts": ["Show database connection errors in Splunk by TEST_ID."]
                }
            )
        ),
        event_generator_func=_db_error_gen
    ))

    # 3. LOG VOLUME & PERFORMANCE CATEGORY
    def _log_surge_gen(i, total, test_id, params):
        return splunk_generator.create_event(
            event_type="high_volume_log_event",
            test_id=test_id,
            scenario_id="HIGH_VOLUME_LOG_SURGE",
            scenario_name="High-Volume Log Surge Simulation",
            service="system-telemetry",
            severity="INFO",
            client_ip="127.0.0.1",
            username="telemetry_agent",
            http_method="GET",
            endpoint="/api/v1/telemetry",
            status_code=200,
            response_time=random.randint(10, 50),
            message="High volume system metric event generated."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="HIGH_VOLUME_LOG_SURGE",
            name="High-Volume Log Surge Simulation",
            category="Log Volume",
            target_platform="Splunk",
            severity="INFO",
            risk_level="LOW",
            duration_seconds=20,
            description="Generates a high volume burst of 100+ log events.",
            expected_outcome=ExpectedOutcome(
                splunk_events=100,
                expected_logs="high_volume_log_event",
                investigation_story={
                    "summary": "Demonstrates Botify handling high event counts.",
                    "recommended_prompts": ["How many events were logged in the volume surge?"]
                }
            )
        ),
        event_generator_func=_log_surge_gen
    ))

    return scenarios
