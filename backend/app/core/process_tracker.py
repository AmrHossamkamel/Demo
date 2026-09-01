import os
import signal
import psutil
import threading
import logging
from typing import Dict, List, Set, Any

logger = logging.getLogger("process_tracker")

class ProcessTracker:
    """
    Safety tracker for all sub-processes, thread pools, and active tasks launched
    by scenario executions. Enforces process isolation and emergency cleanup.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._active_pids: Set[int] = set()
        self._active_scenarios: Dict[str, Any] = {} # scenario_execution_id -> meta
        self._stop_requested: Dict[str, bool] = {}

    def register_process(self, execution_id: str, pid: int, scenario_name: str):
        with self._lock:
            self._active_pids.add(pid)
            if execution_id not in self._active_scenarios:
                self._active_scenarios[execution_id] = {
                    "scenario_name": scenario_name,
                    "pids": set(),
                    "status": "RUNNING"
                }
            self._active_scenarios[execution_id]["pids"].add(pid)
            self._stop_requested[execution_id] = False
        logger.info(f"Registered process PID {pid} for scenario execution {execution_id} ({scenario_name})")

    def is_stop_requested(self, execution_id: str) -> bool:
        with self._lock:
            return self._stop_requested.get(execution_id, False)

    def request_stop(self, execution_id: str):
        with self._lock:
            self._stop_requested[execution_id] = True
            if execution_id in self._active_scenarios:
                self._active_scenarios[execution_id]["status"] = "STOPPING"
        self.stop_execution(execution_id)

    def unregister_execution(self, execution_id: str):
        with self._lock:
            if execution_id in self._active_scenarios:
                pids = self._active_scenarios[execution_id]["pids"]
                self._active_pids.difference_update(pids)
                del self._active_scenarios[execution_id]
            if execution_id in self._stop_requested:
                del self._stop_requested[execution_id]
        logger.info(f"Unregistered execution {execution_id}")

    def stop_execution(self, execution_id: str):
        """Stops all processes tied to a single scenario execution."""
        pids_to_kill = set()
        with self._lock:
            if execution_id in self._active_scenarios:
                pids_to_kill = set(self._active_scenarios[execution_id]["pids"])

        for pid in pids_to_kill:
            self._kill_pid(pid)

    def stop_all() -> List[str]:
        """
        EMERGENCY KILL SWITCH: Terminates all active demo processes instantly and safely.
        """
        stopped_scenarios = []
        with self._lock:
            for exec_id in list(self._stop_requested.keys()):
                self._stop_requested[exec_id] = True

            for exec_id, meta in list(self._active_scenarios.items()):
                stopped_scenarios.append(meta["scenario_name"])

            all_pids = set(self._active_pids)

        for pid in all_pids:
            self._kill_pid(pid)

        with self._lock:
            self._active_pids.clear()
            self._active_scenarios.clear()

        logger.warning(f"EMERGENCY KILL SWITCH ACTIVATED: Stopped {len(stopped_scenarios)} active scenarios and killed PIDs: {all_pids}")
        return stopped_scenarios

    def _kill_pid(self, pid: int):
        try:
            if not psutil.pid_exists(pid):
                return
            proc = psutil.Process(pid)
            # Terminate child processes first
            for child in proc.children(recursive=True):
                try:
                    child.terminate()
                except Exception:
                    pass
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except psutil.TimeoutExpired:
                proc.kill()
        except (psutil.NoSuchProcess, ProcessLookupError):
            pass
        except Exception as e:
            logger.error(f"Error killing PID {pid}: {e}")

    def get_active_summary() -> Dict[str, Any]:
        with self._lock:
            return {
                "active_scenario_count": len(self._active_scenarios),
                "active_process_count": len(self._active_pids),
                "active_scenarios": [
                    {
                        "execution_id": k,
                        "name": v["scenario_name"],
                        "status": v["status"],
                        "pid_count": len(v["pids"])
                    }
                    for k, v in self._active_scenarios.items()
                ]
            }

process_tracker = ProcessTracker()
