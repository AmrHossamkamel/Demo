import time
import random
import logging
from typing import Dict, Any, List
from backend.app.scenarios.base import ScenarioBase, ScenarioMetadata, ExpectedOutcome, ExecutionResult
from backend.app.generators.splunk_generator import splunk_generator
from backend.app.core.process_tracker import process_tracker

logger = logging.getLogger("splunk_scenarios")

class SplunkGenericScenario(ScenarioBase):
    """
    Generic executable scenario builder for all Splunk log-based simulations.
    Generates structured, correlated logs across specified categories.
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

        count = params.get("event_count", self.metadata.expected_outcome.splunk_events or 30)
        delay = params.get("delay_ms", 50) / 1000.0

        try:
            for i in range(count):
                if process_tracker.is_stop_requested(execution_id):
                    logger.info(f"Splunk scenario {self.metadata.id} stopped early.")
                    break
                event = self.event_generator_func(i, count, params)
                if splunk_generator.send_event(event):
                    self._events_sent += 1
                time.sleep(delay)

            status_str = "STOPPED" if process_tracker.is_stop_requested(execution_id) else "COMPLETED"
            return ExecutionResult(
                execution_id=execution_id,
                scenario_id=self.metadata.id,
                status=status_str,
                events_generated=self._events_sent,
                duration_seconds=round(time.time() - start_time, 2),
                telemetry_summary={
                    "splunk_events": self._events_sent,
                    "target_platform": "Splunk",
                    "sourcetype": "botify:demo:json"
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


# --- Factory Builders for Splunk Categories ---

def build_splunk_scenarios() -> List[SplunkGenericScenario]:
    scenarios = []

    # 1. AUTHENTICATION & SECURITY SCENARIOS
    def _brute_force_gen(i, total, params):
        ip = params.get("suspicious_ip", "185.220.101.5")
        user = params.get("target_user", "admin_alrajhi")
        is_last = (i == total - 1)
        if is_last:
            return splunk_generator.create_event(
                event_type="SUCCESSFUL_LOGIN_AFTER_FAILURES",
                service="auth-service",
                severity="CRITICAL",
                client_ip=ip,
                username=user,
                http_method="POST",
                endpoint="/api/v1/auth/login",
                status_code=200,
                message=f"Successful login for user '{user}' after {total-1} consecutive failed attempts from IP {ip}"
            )
        return splunk_generator.create_event(
            event_type="FAILED_LOGIN_ATTEMPT",
            service="auth-service",
            severity="WARNING",
            client_ip=ip,
            username=user,
            http_method="POST",
            endpoint="/api/v1/auth/login",
            status_code=401,
            message=f"Authentication failed for user '{user}' from IP {ip}. Reason: Invalid credential signature."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-sec-bruteforce",
            name="Brute-Force Authentication Simulation",
            category="Authentication & Security",
            target_platform="Splunk",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=30,
            description="Generates consecutive failed login attempts followed by a successful breach login from a suspicious IP.",
            expected_outcome=ExpectedOutcome(
                splunk_events=40,
                dynatrace_signals="Authentication anomaly alert",
                expected_logs="FAILED_LOGIN_ATTEMPT, SUCCESSFUL_LOGIN_AFTER_FAILURES",
                investigation_story={
                    "summary": "Demonstrates Botify discovering brute-force credential stuffing attacks in Splunk logs.",
                    "recommended_prompts": [
                        "Are there any authentication anomalies in Splunk?",
                        "Which IP address initiated brute-force attempts?",
                        "Did any user successfully log in after repeated failures?"
                    ]
                }
            )
        ),
        event_generator_func=_brute_force_gen
    ))

    # SSH Auth Failures
    def _ssh_failures_gen(i, total, params):
        users = ["root", "admin", "ec2-user", "oracle", "deploy"]
        u = random.choice(users)
        return splunk_generator.create_event(
            event_type="SSH_AUTH_FAILURE",
            service="sshd",
            application="system-security",
            severity="HIGH",
            client_ip="194.26.29.112",
            username=u,
            http_method="SSH",
            endpoint="/usr/sbin/sshd",
            status_code=403,
            message=f"Failed password for invalid user {u} from 194.26.29.112 port {random.randint(40000, 60000)} ssh2"
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-sec-ssh-failures",
            name="SSH Authentication Failures",
            category="Authentication & Security",
            target_platform="Splunk",
            severity="WARNING",
            risk_level="LOW",
            duration_seconds=20,
            description="Generates unauthorized SSH root and service account login attempts.",
            expected_outcome=ExpectedOutcome(
                splunk_events=35,
                expected_logs="SSH_AUTH_FAILURE",
                investigation_story={
                    "summary": "Showcases Botify identifying unauthorized SSH scanning.",
                    "recommended_prompts": ["Show SSH login failure evidence in Splunk."]
                }
            )
        ),
        event_generator_func=_ssh_failures_gen
    ))

    # Privilege Escalation
    def _priv_esc_gen(i, total, params):
        return splunk_generator.create_event(
            event_type="PRIVILEGE_ESCALATION_ATTEMPT",
            service="sudo",
            application="security-audit",
            severity="CRITICAL",
            client_ip="10.0.4.52",
            username="app_user",
            http_method="EXEC",
            endpoint="/usr/bin/sudo",
            status_code=403,
            message="USER=app_user ; COMMAND=/usr/bin/python3 -c import os; os.setuid(0); os.system('/bin/sh') ; TTY=pts/1"
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-sec-priv-esc",
            name="Privilege Escalation Simulation",
            category="Authentication & Security",
            target_platform="Splunk",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=15,
            description="Simulates suspicious sudo executions trying to gain root privilege.",
            expected_outcome=ExpectedOutcome(
                splunk_events=20,
                expected_logs="PRIVILEGE_ESCALATION_ATTEMPT",
                investigation_story={
                    "summary": "Highlights Botify detecting insider privilege escalation attempts.",
                    "recommended_prompts": ["What privilege escalation events occurred recently?"]
                }
            )
        ),
        event_generator_func=_priv_esc_gen
    ))

    # 2. APPLICATION SCENARIOS
    def _app_http500_gen(i, total, params):
        endpoints = ["/api/v1/payments/process", "/api/v1/transfers", "/api/v1/accounts/query"]
        ep = random.choice(endpoints)
        return splunk_generator.create_event(
            event_type="HTTP_SERVER_ERROR",
            service="payment-service",
            severity="ERROR",
            client_ip=f"10.0.2.{random.randint(10, 200)}",
            username=f"user_{random.randint(1000, 9999)}",
            http_method="POST",
            endpoint=ep,
            status_code=500,
            response_time=random.randint(1200, 4500),
            message=f"HTTP 500 Internal Server Error processing request on {ep}. NullPointer in TransactionHandler."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-app-http500",
            name="HTTP 500 Server Errors Burst",
            category="Application",
            target_platform="Splunk",
            severity="ERROR",
            risk_level="LOW",
            duration_seconds=25,
            description="Generates a stream of HTTP 500 internal server error logs across application endpoints.",
            expected_outcome=ExpectedOutcome(
                splunk_events=50,
                expected_logs="HTTP_SERVER_ERROR",
                investigation_story={
                    "summary": "Demonstrates Botify aggregating HTTP 500 errors and mapping affected endpoints.",
                    "recommended_prompts": ["What are the main HTTP 500 errors in Splunk?", "Which endpoints are failing?"]
                }
            )
        ),
        event_generator_func=_app_http500_gen
    ))

    # Database Connection Errors
    def _db_errors_gen(i, total, params):
        return splunk_generator.create_event(
            event_type="DATABASE_CONNECTION_ERROR",
            service="payment-service",
            severity="CRITICAL",
            client_ip="10.0.1.15",
            username="db_pool_worker",
            http_method="DB_QUERY",
            endpoint="jdbc:postgresql://db-primary.alrajhi.internal:5432/banking",
            status_code=504,
            response_time=5000,
            message="FATAL: HikariPool-1 - Connection is not available, request timed out after 5000ms. Max pool size (50) reached."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-app-db-errors",
            name="Database Connection Errors",
            category="Application",
            target_platform="Splunk",
            severity="CRITICAL",
            risk_level="LOW",
            duration_seconds=30,
            description="Simulates database connection pool starvation and timeout error logs.",
            expected_outcome=ExpectedOutcome(
                splunk_events=45,
                expected_logs="DATABASE_CONNECTION_ERROR",
                investigation_story={
                    "summary": "Shows Botify pinpointing database pool exhaustion as root cause.",
                    "recommended_prompts": ["Are there any database errors reported in Splunk?"]
                }
            )
        ),
        event_generator_func=_db_errors_gen
    ))

    # 3. INFRASTRUCTURE SCENARIOS
    def _infra_cpu_warning_gen(i, total, params):
        usage = random.randint(85, 98)
        return splunk_generator.create_event(
            event_type="INFRASTRUCTURE_RESOURCE_WARNING",
            service="system-monitor",
            application="host-metrics",
            severity="WARNING",
            client_ip="127.0.0.1",
            username="monitoring_agent",
            http_method="METRIC",
            endpoint="/sys/devices/system/cpu",
            status_code=200,
            message=f"CPU Utilization Threshold Exceeded: Host CPU at {usage}% load across all cores."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-infra-cpu-warning",
            name="CPU Usage Warning Simulation",
            category="Infrastructure",
            target_platform="Splunk",
            severity="WARNING",
            risk_level="LOW",
            duration_seconds=20,
            description="Generates system metric warning logs indicating high CPU load.",
            expected_outcome=ExpectedOutcome(
                splunk_events=30,
                expected_logs="INFRASTRUCTURE_RESOURCE_WARNING",
                investigation_story={
                    "summary": "Demonstrates Botify reporting CPU load warnings.",
                    "recommended_prompts": ["Did Splunk capture any infrastructure warnings?"]
                }
            )
        ),
        event_generator_func=_infra_cpu_warning_gen
    ))

    # 4. OBSERVABILITY SCENARIOS
    def _obs_log_volume_spike_gen(i, total, params):
        return splunk_generator.create_event(
            event_type="LOG_VOLUME_SPIKE_EVENT",
            service="api-gateway",
            severity="INFO",
            client_ip=f"10.0.5.{random.randint(1, 250)}",
            username="gateway_proxy",
            http_method="GET",
            endpoint="/api/v1/transfers/list",
            status_code=200,
            response_time=random.randint(30, 90),
            message="Gateway request routed successfully."
        )

    scenarios.append(SplunkGenericScenario(
        metadata=ScenarioMetadata(
            id="splunk-obs-volume-spike",
            name="Log Volume Spike Generator",
            category="Observability",
            target_platform="Splunk",
            severity="INFO",
            risk_level="LOW",
            duration_seconds=20,
            description="Generates a sudden high-volume surge of application telemetry events.",
            expected_outcome=ExpectedOutcome(
                splunk_events=120,
                expected_logs="LOG_VOLUME_SPIKE_EVENT",
                investigation_story={
                    "summary": "Demonstrates Botify detecting log ingestion volume anomalies.",
                    "recommended_prompts": ["Was there a log volume spike recently?"]
                }
            )
        ),
        event_generator_func=_obs_log_volume_spike_gen
    ))

    return scenarios
