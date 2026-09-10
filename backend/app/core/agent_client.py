"""Authenticated client for the remote workload agent."""

from __future__ import annotations

from typing import Any, Mapping

import requests

from backend.app.config import settings
from backend.app.core.target_manager import Target


class AgentClientError(RuntimeError):
    """Safe, user-facing failure communicating with an agent."""


class AgentClient:
    def __init__(self, target: Target, timeout: float | None = None) -> None:
        self.target = target
        self._token = settings.BOTIFY_AGENT_TOKEN
        self.timeout = timeout if timeout is not None else settings.BOTIFY_AGENT_TIMEOUT_SECONDS

    @property
    def base_url(self) -> str:
        return f"{self.target.protocol}://{self.target.host}:{self.target.port}"

    def _request(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = requests.request(
                method, f"{self.base_url}{path}", json=payload, headers=headers, timeout=self.timeout
            )
        except requests.Timeout as exc:
            raise AgentClientError("The remote agent request timed out.") from exc
        except requests.RequestException as exc:
            raise AgentClientError("The remote agent could not be reached.") from exc
        if response.status_code == 401 or response.status_code == 403:
            raise AgentClientError("The remote agent rejected authentication.")
        if not 200 <= response.status_code < 300:
            raise AgentClientError(f"The remote agent returned HTTP {response.status_code}.")
        try:
            return response.json()
        except ValueError:
            return {}

    def health(self) -> Any:
        return self._request("GET", "/health")

    def list_running(self) -> Any:
        return self._request("GET", "/api/workload/running")

    def stop_workload(self, execution_id: str) -> Any:
        return self._request("POST", "/api/workload/stop", {"executionId": execution_id})

    def stop_all(self) -> Any:
        return self._request("POST", "/api/workload/stop-all")

    def start_workload(self, execution_id: str, workload: Mapping[str, Any]) -> Any:
        return self._request("POST", "/api/workload/start", {"executionId": execution_id, "workload": workload})
