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

class SplunkGenerator:
    """
    Generates structured, searchable Splunk log events and transmits them
    via local JSON log stream, CSV export stream (for manual upload), and Splunk HEC.
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

        # Initialize CSV header if file doesn't exist
        if not os.path.exists(self.primary_csv_file):
            try:
                with open(self.primary_csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "timestamp", "host", "source", "sourcetype", "service",
                        "application", "severity", "event_type", "event_id",
                        "client_ip", "username", "http_method", "endpoint",
                        "status_code", "response_time", "message"
                    ])
            except Exception as e:
                logger.error(f"Failed to initialize CSV log file: {e}")

        try:
            os.makedirs(os.path.dirname(self.sys_log_file), exist_ok=True)
        except Exception:
            pass

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

        # 2. Append to local CSV file (./data/logs/splunk_events.csv) for direct CSV import
        try:
            with open(self.primary_csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    event_data.get("timestamp"),
                    event_data.get("host"),
                    event_data.get("source"),
                    event_data.get("sourcetype"),
                    event_data.get("service"),
                    event_data.get("application"),
                    event_data.get("severity"),
                    event_data.get("event_type"),
                    event_data.get("event_id"),
                    event_data.get("client_ip"),
                    event_data.get("username"),
                    event_data.get("http_method"),
                    event_data.get("endpoint"),
                    event_data.get("status_code"),
                    event_data.get("response_time"),
                    event_data.get("message")
                ])
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
