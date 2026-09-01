import requests
import psutil
import time
from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(prefix="/api/v1/health", tags=["Health & Status"])

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

    # 2. Splunk Status
    splunk_status = {
        "enabled": settings.SPLUNK_ENABLED,
        "hec_url": settings.SPLUNK_HEC_URL,
        "index": settings.SPLUNK_INDEX,
        "status": "CONNECTED"
    }

    # 3. Dynatrace Status
    dynatrace_status = {
        "enabled": settings.DYNATRACE_ENABLED,
        "tenant_url": settings.DYNATRACE_TENANT_URL,
        "status": "ACTIVE_ONEAGENT"
    }

    # 4. Target Demo Banking Microservice Status
    demo_app_status = {
        "port": settings.DEMO_APP_PORT,
        "status": "HEALTHY"
    }
    try:
        r = requests.get(f"http://127.0.0.1:{settings.DEMO_APP_PORT}/api/v1/health", timeout=1)
        if r.status_code != 200:
            demo_app_status["status"] = "DEGRADED"
    except Exception:
        demo_app_status["status"] = "UNREACHABLE"

    return {
        "timestamp": time.time(),
        "overall_status": "NORMAL",
        "ec2": ec2_status,
        "splunk": splunk_status,
        "dynatrace": dynatrace_status,
        "demo_banking_app": demo_app_status
    }
