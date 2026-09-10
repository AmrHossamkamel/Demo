"""Persistent management of local and remote workload targets."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Literal, Mapping
from urllib.parse import urlsplit

TargetType = Literal["local", "remote-agent"]
_CANONICAL_TARGET_TYPES: dict[str, TargetType] = {
    "local": "local",
    "remote-agent": "remote-agent",
    "ec2-agent": "remote-agent",
    "agent": "remote-agent",
}


class TargetError(ValueError):
    """Raised when a target cannot be created or persisted."""


@dataclass(frozen=True)
class Target:
    id: str
    name: str
    type: TargetType
    host: str
    port: int
    protocol: Literal["http", "https"]
    enabled: bool = True


def _validate_identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetError(f"{field} is required.")
    value = value.strip()
    if len(value) > 128 or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for ch in value):
        raise TargetError(f"{field} must contain only letters, numbers, '.', '_' or '-'.")
    return value


def _validate_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetError("name is required.")
    value = value.strip()
    if len(value) > 128:
        raise TargetError("name must be 128 characters or fewer.")
    return value


def _normalize_host(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TargetError("host is required.")
    host = value.strip()
    parsed = urlsplit(f"//{host}")
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise TargetError("host must be a hostname or IP address without a port.") from exc
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise TargetError("host must be a hostname or IP address without a path, query, or userinfo.")
    if not parsed.hostname or parsed_port is not None:
        raise TargetError("host must be a hostname or IP address without a port.")
    return parsed.hostname.lower().rstrip(".")


def _normalize_protocol(value: Any) -> Literal["http", "https"]:
    if not isinstance(value, str) or value.strip().lower() not in ("http", "https"):
        raise TargetError("protocol must be 'http' or 'https'.")
    return value.strip().lower()  # type: ignore[return-value]


def _target_from_mapping(raw: Mapping[str, Any]) -> Target:
    raw_type = raw.get("type")
    if not isinstance(raw_type, str) or raw_type.strip() not in _CANONICAL_TARGET_TYPES:
        raise TargetError("type must be one of: 'local', 'remote-agent', 'ec2-agent', 'agent'.")
    target_type: TargetType = _CANONICAL_TARGET_TYPES[raw_type.strip()]
    target = Target(
        id=_validate_identifier(raw.get("id"), "id"),
        name=_validate_name(raw.get("name")),
        type=target_type,
        host=_normalize_host(raw.get("host")),
        port=raw.get("port"),
        protocol=_normalize_protocol(raw.get("protocol")),
        enabled=bool(raw.get("enabled", True)),
    )
    if not isinstance(target.port, int) or isinstance(target.port, bool) or not 1 <= target.port <= 65535:
        raise TargetError("port must be an integer from 1 to 65535.")
    if target.type == "local" and target.id != "local":
        raise TargetError("The local target must use id 'local'.")
    return target


class TargetManager:
    """Thread-safe target store with an immutable built-in local target."""

    def __init__(self, store_path: str | os.PathLike[str], local_port: int = 9000) -> None:
        self.store_path = Path(store_path)
        self.local_target = Target("local", "Local", "local", "127.0.0.1", local_port, "http", True)
        self._lock = RLock()
        self._targets: dict[str, Target] = {}
        self._load()

    @classmethod
    def from_settings(cls, settings: Any) -> "TargetManager":
        return cls(settings.TARGETS_STORE_PATH, getattr(settings, "PORT", 9000))

    def _load(self) -> None:
        loaded: list[Any] = []
        try:
            if self.store_path.exists():
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                loaded = data.get("targets", []) if isinstance(data, dict) else data
                if not isinstance(loaded, list):
                    loaded = []
        except (OSError, ValueError, TypeError):
            loaded = []
        targets: dict[str, Target] = {"local": self.local_target}
        for raw in loaded:
            try:
                target = _target_from_mapping(raw)
                if target.id != "local" and target.type == "remote-agent" and target.id not in targets:
                    targets[target.id] = target
            except (TargetError, AttributeError):
                continue
        self._targets = targets

    def _persist(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"targets": [asdict(target) for target in self._targets.values()]}
        fd, temporary = tempfile.mkstemp(prefix=f".{self.store_path.name}.", suffix=".tmp", dir=self.store_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.store_path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def list_targets(self) -> list[Target]:
        with self._lock:
            return list(self._targets.values())

    def get_target(self, target_id: str) -> Target | None:
        with self._lock:
            return self._targets.get(target_id)

    def create_target(self, values: Mapping[str, Any]) -> Target:
        target = _target_from_mapping({**values, "type": "remote-agent"})
        with self._lock:
            if target.id in self._targets:
                raise TargetError(f"Target id '{target.id}' already exists.")
            self._targets[target.id] = target
            try:
                self._persist()
            except Exception:
                del self._targets[target.id]
                raise
            return target

    def remove_target(self, target_id: str) -> None:
        with self._lock:
            if target_id == "local":
                raise TargetError("The local target cannot be removed.")
            if target_id not in self._targets:
                raise KeyError(target_id)
            removed = self._targets.pop(target_id)
            try:
                self._persist()
            except Exception:
                self._targets[target_id] = removed
                raise
