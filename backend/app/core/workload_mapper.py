"""Map scenario definitions to remote workload types and parameters."""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger("workload_mapper")

# Supported remote workload types based on agent capabilities
SUPPORTED_REMOTE_WORKLOAD_TYPES = {
    "cpu_stress",
    "memory_stress",
    "disk_io_stress",
    "network_stress",
}


class WorkloadMapperError(Exception):
    """Raised when a scenario cannot be mapped to a remote workload."""


def map_scenario_to_workload(
    scenario_id: str,
    scenario_name: str,
    target_platform: str,
    parameters: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Map a local scenario to a remote workload definition.
    Returns None for local-only scenarios, raises WorkloadMapperError for incompatible remote scenarios.
    """

    # Dynatrace CPU stress scenario
    if scenario_id == "DT_CPU_STRESS":
        return {
            "type": "cpu_stress",
            "duration_seconds": parameters.get("duration_seconds", 30),
            "target_cpu_percent": parameters.get("target_cpu_percent", 75),
        }

    # Dynatrace memory stress scenario
    if scenario_id == "DT_MEMORY_STRESS":
        return {
            "type": "memory_stress",
            "duration_seconds": parameters.get("duration_seconds", 30),
            "memory_mb": parameters.get("memory_mb", 512),
        }

    # Dynatrace disk I/O scenario
    if scenario_id == "DT_DISK_IO_STRESS":
        return {
            "type": "disk_io_stress",
            "duration_seconds": parameters.get("duration_seconds", 30),
            "file_size_mb": parameters.get("file_size_mb", 100),
        }

    # Dynatrace network stress scenario
    if scenario_id == "DT_NETWORK_STRESS":
        return {
            "type": "network_stress",
            "duration_seconds": parameters.get("duration_seconds", 30),
            "request_rate": parameters.get("request_rate", 100),
        }

    # Splunk and compound scenarios are typically local-only
    if "SPLUNK" in scenario_id or "compound" in scenario_id.lower():
        raise WorkloadMapperError(
            f"Scenario '{scenario_name}' ({scenario_id}) is not supported for remote execution."
        )

    # Unknown scenario - attempt local execution only
    logger.warning(f"No remote mapping for scenario {scenario_id}, will use local execution only.")
    raise WorkloadMapperError(
        f"Scenario '{scenario_name}' ({scenario_id}) does not have a remote workload mapping."
    )


def can_execute_remotely(scenario_id: str) -> bool:
    """Check if a scenario can potentially execute remotely."""
    try:
        map_scenario_to_workload(scenario_id, "", "", {})
        return True
    except WorkloadMapperError:
        return False
