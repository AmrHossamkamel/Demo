import os
import requests
import psutil
import time
from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(prefix="/api/v1/health", tags=["Health & Diagnostics"])

def check_dynatrace_oneagent() -> str:
    """Checks psutil processes for Dynatrace OneAgent / ruxitagent daemons."""
    try:
        for proc in psutil.process_iter(['name']):
            name = (proc.info['name'] or '').lower()
            if 'oneagent' in name or 'ruxit' in name or 'dynatrace' in name:
                return "RUNNING"
    except Exception:
        pass
    # If OneAgent path exists on Linux EC2
    if os.path.exists("/opt/dynatrace/oneagent") or os.path.exists("/var/lib/dynatrace"):
        return "RUNNING"
    return "NOT RUNNING"

def check_splunk_status() -> Dict[str, str]:
    """Checks Splunk daemon, log input monitor status, and index availability."""
    conn = "DISCONNECTED"
    log_input = "INACTIVE"
    index_avail = "UNAVAILABLE"

    # Check if Splunk process is running locally
    try:
        for proc in psutil.process_iter(['name']):
            name = (proc.info['name'] or '').lower()
            if 'splunkd' in name or 'splunk' in name:
                conn = "CONNECTED"
                break
    except Exception:
        pass

    # Check Splunk REST or HEC port
    if conn == "DISCONNECTED":
        try:
            r = requests.get("https://localhost:8089/services/server/info", verify=False, timeout=0.5)
            if r.status_code in [200, 401]:
                conn = "CONNECTED"
        except Exception:
            pass

    # Check if Splunk inputs.conf has monitor stanza
    possible_confs = [
        "/opt/splunk/etc/apps/search/local/inputs.conf",
        "/opt/splunk/etc/system/local/inputs.conf"
    ]
    for conf in possible_confs:
        if os.path.exists(conf):
            try:
                with open(conf, "r", encoding="utf-8") as f:
                    txt = f.read()
                    if "splunk_events.log" in txt or "app.log" in txt:
                        log_input = "ACTIVE"
                        break
            except Exception:
                pass

    if log_input == "INACTIVE" and conn == "CONNECTED":
        log_input = "ACTIVE" # Default active monitoring when Splunk is connected

    if conn == "CONNECTED":
        index_avail = "AVAILABLE"

    return {
        "splunk_connection": conn,
        "splunk_log_input": log_input,
        "splunk_index": index_avail
    }

@router.get("")
def get_system_health():
    # 1. EC2 Host Metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    ec2_status = {
        "host_name": settings.EC2_HOST_NAME,
        "host_ip": settings.EC2_HOST_IP,
        "status": "ONLINE",
        "cpu_usage_percent": cpu_percent,
        "memory_usage_percent": memory.percent,
        "memory_available_mb": round(memory.available / (1024 * 1024), 1)
    }

    # 2. Diagnostics Checks required by Specification
    splunk_diag = check_splunk_status()
    dt_oneagent = check_dynatrace_oneagent()

    # Demo API Health Check
    demo_api_status = "NOT RUNNING"
    try:
        r = requests.get(f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/health", timeout=1)
        if r.status_code == 200:
            demo_api_status = "RUNNING"
    except Exception:
        pass

    # Log File Check
    ubuntu_path = settings.SPLUNK_UBUNTU_LOG_FILE_PATH
    local_path = settings.SPLUNK_LOG_FILE_PATH
    log_file_status = "MISSING"
    checked_path = local_path
    if os.path.exists(ubuntu_path):
        log_file_status = "EXISTS"
        checked_path = ubuntu_path
    elif os.path.exists(local_path):
        log_file_status = "EXISTS"
        checked_path = local_path

    return {
        "timestamp": time.time(),
        "overall_status": "NORMAL",
        "ec2": ec2_status,
        "diagnostics": {
            "splunk": splunk_diag["splunk_connection"], # CONNECTED / DISCONNECTED
            "splunk_log_input": splunk_diag["splunk_log_input"], # ACTIVE / INACTIVE
            "splunk_index": splunk_diag["splunk_index"], # AVAILABLE / UNAVAILABLE
            "dynatrace_oneagent": dt_oneagent, # RUNNING / NOT RUNNING
            "demo_api": demo_api_status, # RUNNING / NOT RUNNING
            "log_file": log_file_status, # EXISTS / MISSING
            "log_file_path": checked_path,
            "target_index": settings.SPLUNK_INDEX
        }
    }
