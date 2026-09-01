import time
import math
import random
import logging
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

logger = logging.getLogger("demo_banking_service")

demo_app = FastAPI(
    title="Botify Demo Target Microservice",
    description="Dedicated target microservice for operational & Dynatrace observability fault injection.",
    version="1.1.0"
)

# Dynamic Fault Injection State
fault_state = {
    "latency_ms": 0,
    "force_500_rate": 0.0,
    "force_404_rate": 0.0,
    "force_db_timeout": False,
    "force_exception": False,
    "service_stopped": False
}

class FaultInjectionConfig(BaseModel):
    latency_ms: Optional[int] = 0
    force_500_rate: Optional[float] = 0.0
    force_404_rate: Optional[float] = 0.0
    force_db_timeout: Optional[bool] = False
    force_exception: Optional[bool] = False
    service_stopped: Optional[bool] = False

@demo_app.post("/api/v1/demo/fault-injection")
def set_fault_injection(config: FaultInjectionConfig):
    global fault_state
    fault_state.update(config.dict(exclude_unset=True))
    logger.warning(f"Demo Service fault state updated: {fault_state}")
    return {"status": "success", "active_faults": fault_state}

@demo_app.post("/api/v1/demo/reset-faults")
def reset_faults():
    global fault_state
    fault_state = {
        "latency_ms": 0,
        "force_500_rate": 0.0,
        "force_404_rate": 0.0,
        "force_db_timeout": False,
        "force_exception": False,
        "service_stopped": False
    }
    return {"status": "success", "message": "All fault injections reset to normal baseline."}

# SPECIFIC DEMO ENDPOINTS FOR DYNATRACE ONEAGENT MONITORING
@demo_app.get("/normal")
@demo_app.get("/api/v1/normal")
def normal_endpoint():
    return {"status": "200 OK", "message": "Normal response from demo service.", "timestamp": time.time()}

@demo_app.get("/error")
@demo_app.get("/api/v1/error")
def error_endpoint():
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": "Simulated 500 error on demo service for Dynatrace observation."}
    )

@demo_app.get("/slow")
@demo_app.get("/api/v1/slow")
def slow_endpoint(delay_ms: int = 2500):
    time.sleep(delay_ms / 1000.0)
    return {"status": "200 OK", "message": f"Slow response completed after {delay_ms}ms.", "latency_ms": delay_ms}

@demo_app.get("/high-load")
@demo_app.get("/api/v1/high-load")
def high_load_endpoint(duration_ms: int = 500):
    start = time.time()
    while (time.time() - start) < (duration_ms / 1000.0):
        _ = math.sqrt(12345.6789) * math.sin(987.65)
    return {"status": "200 OK", "message": "High CPU load iteration completed.", "duration_ms": duration_ms}

@demo_app.middleware("http")
async def fault_injection_middleware(request: Request, call_next):
    if fault_state.get("service_stopped") and not request.url.path.startswith("/api/v1/demo"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Service Unavailable", "message": "Demo Service is currently stopped."}
        )

    # 1. Apply simulated latency
    latency = fault_state.get("latency_ms", 0)
    if latency > 0 and not request.url.path.startswith("/api/v1/demo"):
        time.sleep(latency / 1000.0)

    # 2. Apply forced exceptions
    if fault_state.get("force_exception") and not request.url.path.startswith("/api/v1/demo"):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "UnhandledApplicationException",
                "message": "Critical failure in banking core thread execution context.",
                "traceback": "NullPointerException at com.alrajhi.banking.PaymentCore.process(PaymentCore.java:142)"
            }
        )

    # 3. Apply DB Timeout
    if fault_state.get("force_db_timeout") and not request.url.path.startswith("/api/v1/demo"):
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "DatabaseConnectionTimeout", "message": "Database connection pool exhausted after 3000ms"}
        )

    # 4. Apply HTTP 500 error rate
    rate_500 = fault_state.get("force_500_rate", 0.0)
    if rate_500 > 0 and random.random() < rate_500 and not request.url.path.startswith("/api/v1/demo"):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "message": "Payment processing gateway failed unexpectedly."}
        )

    # 5. Apply HTTP 404 error rate
    rate_404 = fault_state.get("force_404_rate", 0.0)
    if rate_404 > 0 and random.random() < rate_404 and not request.url.path.startswith("/api/v1/demo"):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "ResourceNotFound", "message": "The requested account transaction resource was not found."}
        )

    response = await call_next(request)
    return response

# Standard Banking Endpoints
@demo_app.get("/api/v1/health")
def health():
    return {"status": "HEALTHY", "service": "Demo Target Core", "timestamp": time.time()}

@demo_app.post("/api/v1/auth/login")
def login(payload: Dict[str, Any]):
    username = payload.get("username", "guest")
    password = payload.get("password", "")
    if password == "CorrectPassword123!":
        return {"status": "SUCCESS", "token": f"jwt-token-{random.randint(1000, 9999)}", "user": username}
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"status": "FAILURE", "error": "InvalidCredentials", "message": "Authentication failed."}
    )

@demo_app.post("/api/v1/payments/process")
def process_payment(payload: Dict[str, Any]):
    account = payload.get("account", "ACC-99210")
    amount = payload.get("amount", 100.0)
    return {
        "status": "APPROVED",
        "transaction_id": f"TXN-{random.randint(100000, 999999)}",
        "account": account,
        "amount": amount,
        "currency": "SAR"
    }

@demo_app.get("/api/v1/accounts/{account_id}")
def get_account(account_id: str):
    return {
        "account_id": account_id,
        "holder": "Demo Client",
        "balance": 250000.00,
        "currency": "SAR",
        "type": "SAVINGS"
    }

@demo_app.get("/api/v1/transfers")
def list_transfers():
    return {
        "transfers": [
            {"id": "TR-101", "amount": 5000.0, "status": "COMPLETED"},
            {"id": "TR-102", "amount": 12500.0, "status": "COMPLETED"}
        ]
    }
