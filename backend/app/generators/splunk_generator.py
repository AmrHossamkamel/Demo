import os
import time
import json
import csv
import uuid
import logging
import requests
import datetime
from typing import Dict, Any, List, Optional
from backend.app.config import settings

logger = logging.getLogger("splunk_generator")

CSV_HEADER = [
    "timestamp", "host", "source", "sourcetype", "service",
    "application", "severity", "event_type", "event_id",
    "client_ip", "username", "http_method", "endpoint",
    "status_code", "response_time", "message"
]

class SplunkGenerator:
    """
    Generates rich, structured Splunk log events and transmits them
    via local JSON log stream, system log file, CSV export stream, and Splunk HEC.
    Directly targets the 'main' index for seamless Botify AI integration.
    """
    def __init__(self):
        self.hec_url = settings.SPLUNK_HEC_URL
        self.hec_token = settings.SPLUNK_HEC_TOKEN
        self.index = settings.SPLUNK_INDEX or "main"
        self.primary_log_file = settings.SPLUNK_LOG_FILE_PATH # ./data/logs/splunk_events.log
        self.primary_csv_file = getattr(settings, "SPLUNK_CSV_FILE_PATH", "./data/logs/splunk_events.csv")
        self.sys_log_file = "/var/log/botify_demo/app.log"

        os.makedirs(os.path.dirname(self.primary_log_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.primary_csv_file), exist_ok=True)

        # Initialize CSV file with header and realistic seed demo data if file is empty
        self._ensure_csv_file_populated()

        try:
            os.makedirs(os.path.dirname(self.sys_log_file), exist_ok=True)
        except Exception:
            pass

    def _ensure_csv_file_populated(self):
        """Ensures CSV file exists, has clean headers, and contains initial demo log records."""
        need_header = not os.path.exists(self.primary_csv_file) or os.path.getsize(self.primary_csv_file) == 0
        if need_header:
            try:
                with open(self.primary_csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_HEADER)
                    # Write seed demo events so CSV is immediately populated with full banking errors
                    seed_events = [
                        self.create_event(
                            event_type="DATABASE_CONNECTION_TIMEOUT",
                            service="payment-service",
                            severity="CRITICAL",
                            client_ip="10.0.3.15",
                            username="usr_8921",
                            http_method="POST",
                            endpoint="/api/v1/payments/process",
                            status_code=504,
                            response_time=3200,
                            message="DB_CONNECTION_TIMEOUT on /api/v1/payments: HikariPool connection exhausted after 3000ms."
                        ),
                        self.create_event(
                            event_type="FAILED_LOGIN_ATTEMPT",
                            service="auth-service",
                            severity="WARNING",
                            client_ip="185.220.101.5",
                            username="admin_alrajhi",
                            http_method="POST",
                            endpoint="/api/v1/auth/login",
                            status_code=401,
                            response_time=120,
                            message="Authentication failed for user admin_alrajhi from IP 185.220.101.5. Invalid credential signature."
                        ),
                        self.create_event(
                            event_type="HTTP_SERVER_ERROR",
                            service="payment-service",
                            severity="ERROR",
                            client_ip="10.0.2.45",
                            username="usr_1042",
                            http_method="POST",
                            endpoint="/api/v1/payments/process",
                            status_code=500,
                            response_time=2400,
                            message="HTTP 500 Internal Server Error processing payment request. NullPointer in TransactionCore.java:142"
                        )
                    ]
                    for ev in seed_events:
                        writer.writerow([ev.get(col, "") for col in CSV_HEADER])
            except Exception as e:
                logger.error(f"Failed to initialize CSV file: {e}")

    def create_event(
        self,
        event_type: str,
        service: str = "payment-service",
        application: str = "demo-banking-app",
        severity: str = "INFO",
        client_ip: str = "192.168.1.100",
        username: str = "system",
        http_method: str = "GET",
        endpoint: str = "/api/v1/health",
        status_code: int = 200,
        response_time: int = 45,
        message: str = "Operation completed successfully",
        sourcetype: str = "botify:demo:json",
        extra_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        now = datetime.datetime.utcnow()
        event_data = {
            "timestamp": now.isoformat() + "Z",
            "epoch_time": time.time(),
            "host": settings.EC2_HOST_NAME,
            "source": f"botify://{service}/{application}",
            "sourcetype": sourcetype,
            "service": service,
            "application": application,
            "severity": severity,
            "event_type": event_type,
            "event_id": f"evt-{uuid.uuid4().hex[:10]}",
            "client_ip": client_ip,
            "username": username,
            "http_method": http_method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time": response_time,
            "message": message
        }

        if extra_fields:
            event_data.update(extra_fields)

        return event_data

    def send_event(self, event_data: Dict[str, Any]) -> bool:
        log_line = json.dumps(event_data) + "\n"

        # 1. Write to local project log file (./data/logs/splunk_events.log)
        try:
            with open(self.primary_log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            logger.error(f"Failed to write log to primary file {self.primary_log_file}: {e}")

        # 2. Append to local CSV file (./data/logs/splunk_events.csv) with all fields
        try:
            with open(self.primary_csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([event_data.get(col, "") for col in CSV_HEADER])
        except Exception as e:
            logger.error(f"Failed to write to CSV file {self.primary_csv_file}: {e}")

        # 3. Write to system log file (/var/log/botify_demo/app.log) if writable
        try:
            if os.path.exists(os.path.dirname(self.sys_log_file)):
                with open(self.sys_log_file, "a", encoding="utf-8") as f:
                    f.write(log_line)
        except Exception:
            pass

        # 4. Transmit via HEC directly into index='main' if configured
        if settings.SPLUNK_ENABLED and self.hec_url and "demo-splunk-hec-token" not in self.hec_token:
            try:
                payload = {
                    "time": event_data.get("epoch_time", time.time()),
                    "host": event_data["host"],
                    "source": event_data["source"],
                    "sourcetype": event_data["sourcetype"],
                    "index": self.index or "main",
                    "event": event_data
                }
                headers = {
                    "Authorization": f"Splunk {self.hec_token}",
                    "Content-Type": "application/json"
                }
                requests.post(self.hec_url, json=payload, headers=headers, timeout=1)
            except Exception:
                pass

        return True

    def send_batch(self, events: List[Dict[str, Any]]) -> int:
        count = 0
        for ev in events:
            if self.send_event(ev):
                count += 1
        return count

splunk_generator = SplunkGenerator()
