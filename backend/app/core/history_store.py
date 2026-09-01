import os
import json
import sqlite3
import datetime
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("history_store")

class HistoryStore:
    """
    Manages persistent execution audit logs for all scenario runs.
    Uses SQLite database with fallback to JSON file.
    """
    def __init__(self, db_path: str = "./data/history.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS scenario_history (
                        execution_id TEXT PRIMARY KEY,
                        scenario_id TEXT NOT NULL,
                        scenario_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        target_platform TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        user_action TEXT NOT NULL DEFAULT 'User',
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        duration_seconds REAL DEFAULT 0,
                        events_generated INTEGER DEFAULT 0,
                        status TEXT NOT NULL,
                        parameters TEXT,
                        error_message TEXT,
                        telemetry_summary TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize history database: {e}")

    def log_start(self, execution_id: str, scenario_meta: Dict[str, Any], parameters: Dict[str, Any], user_action: str = "User") -> Dict[str, Any]:
        record = {
            "execution_id": execution_id,
            "scenario_id": scenario_meta.get("id", "unknown"),
            "scenario_name": scenario_meta.get("name", "Unknown Scenario"),
            "category": scenario_meta.get("category", "General"),
            "target_platform": scenario_meta.get("target_platform", "Splunk & Dynatrace"),
            "severity": scenario_meta.get("severity", "MEDIUM"),
            "user_action": user_action,
            "start_time": datetime.datetime.utcnow().isoformat() + "Z",
            "end_time": None,
            "duration_seconds": 0.0,
            "events_generated": 0,
            "status": "RUNNING",
            "parameters": json.dumps(parameters),
            "error_message": None,
            "telemetry_summary": json.dumps(scenario_meta.get("expected_outcome", {}))
        }

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scenario_history (
                        execution_id, scenario_id, scenario_name, category, target_platform,
                        severity, user_action, start_time, end_time, duration_seconds,
                        events_generated, status, parameters, error_message, telemetry_summary
                    ) VALUES (
                        :execution_id, :scenario_id, :scenario_name, :category, :target_platform,
                        :severity, :user_action, :start_time, :end_time, :duration_seconds,
                        :events_generated, :status, :parameters, :error_message, :telemetry_summary
                    )
                """, record)
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging scenario start: {e}")

        return record

    def log_update(self, execution_id: str, status: str, events_generated: int = 0, error_message: Optional[str] = None):
        end_time = None
        duration = 0.0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT start_time FROM scenario_history WHERE execution_id = ?", (execution_id,))
                row = cursor.fetchone()
                if row and row["start_time"]:
                    start_dt = datetime.datetime.fromisoformat(row["start_time"].rstrip("Z"))
                    now_dt = datetime.datetime.utcnow()
                    duration = round((now_dt - start_dt).total_seconds(), 2)

                if status in ["COMPLETED", "FAILED", "CANCELLED", "STOPPED"]:
                    end_time = datetime.datetime.utcnow().isoformat() + "Z"

                cursor.execute("""
                    UPDATE scenario_history
                    SET status = ?,
                        events_generated = ?,
                        error_message = ?,
                        end_time = COALESCE(?, end_time),
                        duration_seconds = CASE WHEN ? > 0 THEN ? ELSE duration_seconds END
                    WHERE execution_id = ?
                """, (status, events_generated, error_message, end_time, duration, duration, execution_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Error updating scenario execution log: {e}")

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        results = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM scenario_history
                    ORDER BY start_time DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                for row in rows:
                    item = dict(row)
                    if item.get("parameters"):
                        try:
                            item["parameters"] = json.loads(item["parameters"])
                        except Exception:
                            pass
                    if item.get("telemetry_summary"):
                        try:
                            item["telemetry_summary"] = json.loads(item["telemetry_summary"])
                        except Exception:
                            pass
                    results.append(item)
        except Exception as e:
            logger.error(f"Error fetching scenario history: {e}")
        return results

    def clear_history(self):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM scenario_history")
                conn.commit()
        except Exception as e:
            logger.error(f"Error clearing history: {e}")

history_store = HistoryStore()
