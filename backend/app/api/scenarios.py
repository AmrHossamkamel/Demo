from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional, List
from backend.app.core.scenario_engine import ScenarioEngine

router = APIRouter(prefix="/api/v1/scenarios", tags=["Scenarios"])

# Will be initialized on first request
_scenario_engine: Optional[ScenarioEngine] = None

def _get_engine() -> ScenarioEngine:
    global _scenario_engine
    if _scenario_engine is None:
        from backend.app.api.targets import target_manager
        _scenario_engine = ScenarioEngine(target_manager=target_manager)
    return _scenario_engine

@router.get("")
def list_scenarios(category: Optional[str] = Query(None), platform: Optional[str] = Query(None)):
    return {"scenarios": _get_engine().list_scenarios(category=category, platform=platform)}

@router.get("/active")
def get_active_scenarios():
    return {"active_executions": _get_engine().get_active_executions()}

@router.get("/{scenario_id}")
def get_scenario_details(scenario_id: str):
    details = _get_engine().get_scenario(scenario_id)
    if not details:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    return details

@router.post("/{scenario_id}/run")
def run_scenario(scenario_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    params = payload.get("parameters", {}) if payload else {}
    user_action = payload.get("user_action", "User") if payload else "User"
    target_id = payload.get("targetId") or payload.get("target_id") if payload else None
    try:
        res = _get_engine().run_scenario(scenario_id, parameters=params, user_action=user_action, target_id=target_id)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute scenario: {e}")

@router.post("/{execution_id}/stop")
def stop_scenario(execution_id: str):
    success = _get_engine().stop_scenario(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="Active execution not found or already stopped.")
    return {"status": "success", "message": f"Scenario execution {execution_id} stopped."}

@router.post("/stop-all")
def emergency_stop_all():
    stopped_list = _get_engine().stop_all()
    return {
        "status": "EMERGENCY_STOP_ACTIVATED",
        "message": "All active scenario executions and sub-processes have been terminated safely.",
        "stopped_scenarios": stopped_list
    }
