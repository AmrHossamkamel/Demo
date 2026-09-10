import uuid
import time
import threading
import logging
from typing import Dict, Any, List, Optional
from backend.app.scenarios.base import ScenarioBase
from backend.app.scenarios.splunk_scenarios import build_splunk_scenarios
from backend.app.scenarios.dynatrace_scenarios import build_dynatrace_scenarios
from backend.app.scenarios.compound_scenarios import build_compound_scenarios
from backend.app.core.process_tracker import process_tracker
from backend.app.core.history_store import history_store
from backend.app.core.executor import get_executor, ExecutorError, WorkloadExecutor
from backend.app.core.workload_mapper import map_scenario_to_workload, WorkloadMapperError

logger = logging.getLogger("scenario_engine")
class ScenarioEngine:
    """
    Central Manager & Orchestrator for all scenario definitions,
    execution thread lifecycle, history logging, and safety controls.
    Supports both local and target-aware remote execution.
    """
    def __init__(self, target_manager: Optional[Any] = None):
        self._scenarios: Dict[str, ScenarioBase] = {}
        self._active_executions: Dict[str, Dict[str, Any]] = {} # exec_id -> meta
        self._lock = threading.Lock()
        self._target_manager = target_manager
        self._register_all_scenarios()

    def _register_all_scenarios(self):
        # 1. Register Splunk Scenarios
        for s in build_splunk_scenarios():
            self._scenarios[s.metadata.id] = s

        # 2. Register Dynatrace Scenarios
        for s in build_dynatrace_scenarios():
            self._scenarios[s.metadata.id] = s

        # 3. Register Compound Scenarios
        for s in build_compound_scenarios():
            self._scenarios[s.metadata.id] = s

        logger.info(f"Registered total {len(self._scenarios)} scenarios in ScenarioEngine.")

    def list_scenarios(self, category: Optional[str] = None, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        for s_id, s_instance in self._scenarios.items():
            meta = s_instance.metadata.dict()
            if category and category.lower() not in meta["category"].lower():
                continue
            if platform and platform.lower() not in meta["target_platform"].lower():
                continue
            results.append(meta)
        return results

    def get_scenario(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        if scenario_id in self._scenarios:
            return self._scenarios[scenario_id].metadata.dict()
        return None

    def run_scenario(self, scenario_id: str, parameters: Optional[Dict[str, Any]] = None, user_action: str = "User", target_id: Optional[str] = None) -> Dict[str, Any]:
        if scenario_id not in self._scenarios:
            raise ValueError(f"Scenario ID '{scenario_id}' not found.")

        scenario = self._scenarios[scenario_id]
        params = parameters or {}

        if not scenario.validate(params):
            raise ValueError(f"Validation failed for scenario '{scenario_id}'.")

        # Resolve target (default to local)
        target = None
        target_host = "localhost"
        if target_id and self._target_manager:
            target = self._target_manager.get_target(target_id)
            if not target:
                raise ValueError(f"Target '{target_id}' not found.")
            target_host = target.host
        elif target_id and not self._target_manager:
            raise ValueError("Target manager not available. Cannot use remote targets.")

        execution_id = f"exec-{uuid.uuid4().hex[:12]}"
        meta_dict = scenario.metadata.dict()

        # Log start to persistent audit history with target information
        history_store.log_start(
            execution_id,
            meta_dict,
            params,
            user_action=user_action,
            target_id=target_id or "local",
            target_host=target_host
        )

        # Determine executor
        executor = get_executor(target)
        is_remote = target is not None and target.type == "remote-agent"

        with self._lock:
            self._active_executions[execution_id] = {
                "execution_id": execution_id,
                "scenario_id": scenario_id,
                "scenario_name": meta_dict["name"],
                "target_platform": meta_dict["target_platform"],
                "severity": meta_dict["severity"],
                "start_time": time.time(),
                "status": "RUNNING",
                "events_generated": 0,
                "scenario_instance": scenario,
                "executor": executor,
                "is_remote": is_remote,
                "target_id": target_id or "local",
                "target_host": target_host
            }

        # Launch scenario execution in isolated background thread
        thread = threading.Thread(
            target=self._execution_worker,
            args=(execution_id, scenario, params, executor, is_remote),
            daemon=True
        )
        thread.start()

        logger.info(f"Launched scenario execution {execution_id} for '{meta_dict['name']}' on target '{target_id or 'local'}'")
        return {
            "execution_id": execution_id,
            "scenario_id": scenario_id,
            "scenario_name": meta_dict["name"],
            "status": "RUNNING",
            "target_id": target_id or "local",
            "target_host": target_host,
            "message": "Scenario execution launched successfully."
        }

    def _execution_worker(self, execution_id: str, scenario: ScenarioBase, params: Dict[str, Any], executor: WorkloadExecutor, is_remote: bool):
        try:
            if is_remote:
                # Remote execution: map scenario to workload and send to agent
                try:
                    workload = map_scenario_to_workload(
                        scenario.metadata.id,
                        scenario.metadata.name,
                        scenario.metadata.target_platform,
                        params
                    )
                except WorkloadMapperError as e:
                    raise ValueError(str(e))

                try:
                    executor.start_workload(execution_id, workload)
                    # For remote execution, we consider it started successfully
                    with self._lock:
                        if execution_id in self._active_executions:
                            self._active_executions[execution_id]["status"] = "COMPLETED"
                            self._active_executions[execution_id]["events_generated"] = 1
                    history_store.log_update(
                        execution_id=execution_id,
                        status="COMPLETED",
                        events_generated=1,
                        telemetry_summary={"remote_execution": True}
                    )
                except ExecutorError as e:
                    raise ValueError(f"Remote execution failed: {e}")
            else:
                # Local execution
                result = scenario.execute(execution_id, params)
                with self._lock:
                    if execution_id in self._active_executions:
                        self._active_executions[execution_id]["status"] = result.status
                        self._active_executions[execution_id]["events_generated"] = result.events_generated

                history_store.log_update(
                    execution_id=execution_id,
                    status=result.status,
                    events_generated=result.events_generated,
                    error_message=result.error_message
                )
        except Exception as e:
            logger.error(f"Execution error in scenario {execution_id}: {e}")
            history_store.log_update(execution_id=execution_id, status="FAILED", error_message=str(e))
        finally:
            scenario.cleanup()
            process_tracker.unregister_execution(execution_id)
            with self._lock:
                if execution_id in self._active_executions:
                    del self._active_executions[execution_id]

    def stop_scenario(self, execution_id: str) -> bool:
        with self._lock:
            if execution_id in self._active_executions:
                meta = self._active_executions[execution_id]
                scenario = meta["scenario_instance"]
                executor = meta["executor"]
                is_remote = meta["is_remote"]

                if is_remote:
                    try:
                        executor.stop_workload(execution_id)
                    except ExecutorError as e:
                        logger.error(f"Failed to stop remote workload {execution_id}: {e}")
                        history_store.log_update(execution_id, "FAILED", error_message=str(e))
                else:
                    scenario.stop()
                    process_tracker.request_stop(execution_id)

                history_store.log_update(execution_id, "STOPPED")
                return True
        return False

    def stop_all(self) -> List[str]:
        """Emergency stop all active executions (both local and remote)."""
        stopped = []
        with self._lock:
            for exec_id, meta in list(self._active_executions.items()):
                executor = meta["executor"]
                is_remote = meta["is_remote"]

                if is_remote:
                    try:
                        executor.stop_workload(exec_id)
                    except ExecutorError as e:
                        logger.error(f"Failed to stop remote workload {exec_id}: {e}")
                else:
                    meta["scenario_instance"].stop()

                stopped.append(meta["scenario_name"])
                history_store.log_update(exec_id, "CANCELLED", error_message="Emergency Stop All Activated")

        process_tracker.stop_all()

        with self._lock:
            self._active_executions.clear()

        return stopped

    def get_active_executions(self) -> List[Dict[str, Any]]:
        with self._lock:
            res = []
            for exec_id, meta in self._active_executions.items():
                elapsed = round(time.time() - meta["start_time"], 1)
                res.append({
                    "execution_id": exec_id,
                    "scenario_id": meta["scenario_id"],
                    "scenario_name": meta["scenario_name"],
                    "target_platform": meta["target_platform"],
                    "severity": meta["severity"],
                    "status": meta["status"],
                    "elapsed_seconds": elapsed,
                    "events_generated": meta["events_generated"],
                    "target_id": meta.get("target_id", "local"),
                    "target_host": meta.get("target_host", "localhost"),
                    "is_remote": meta.get("is_remote", False)
                })
            return res

