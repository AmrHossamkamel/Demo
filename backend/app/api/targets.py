from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.config import settings
from backend.app.core.agent_client import AgentClient, AgentClientError
from backend.app.core.target_manager import TargetError, TargetManager

router = APIRouter(prefix="/api/v1/targets", tags=["Targets"])
target_manager = TargetManager.from_settings(settings)


class TargetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    type: Literal["remote-agent"] = "remote-agent"
    host: str
    port: int
    protocol: str
    enabled: bool = True


def _public(target: Any) -> dict[str, Any]:
    return {
        "id": target.id, "name": target.name, "type": target.type, "host": target.host,
        "port": target.port, "protocol": target.protocol, "enabled": target.enabled,
    }


@router.get("")
def list_targets() -> dict[str, list[dict[str, Any]]]:
    return {"targets": [_public(target) for target in target_manager.list_targets()]}


@router.post("", status_code=201)
def create_target(payload: TargetCreateRequest) -> dict[str, Any]:
    try:
        return _public(target_manager.create_target(payload.model_dump()))
    except TargetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{target_id}")
def delete_target(target_id: str) -> dict[str, str]:
    try:
        target_manager.remove_target(target_id)
    except TargetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Target not found.") from exc
    return {"status": "success"}


@router.post("/{target_id}/test")
def test_target(target_id: str) -> dict[str, Any]:
    target = target_manager.get_target(target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Target not found.")
    if target.type == "local":
        return {"status": "ok", "target_id": target.id, "message": "Local target is available."}
    try:
        health = AgentClient(target).health()
    except AgentClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"status": "ok", "target_id": target.id, "health": health}
