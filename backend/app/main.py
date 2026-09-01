import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.api.scenarios import router as scenarios_router
from backend.app.api.health import router as health_router
from backend.app.api.history import router as history_router
from backend.app.demo_app.banking_service import demo_app

app = FastAPI(
    title="Botify Observability Demo Testing Platform",
    description="Enterprise Demo Engine for Splunk & Dynatrace Telemetry Generation and Botify AI Investigation.",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Main API Routers
app.include_router(scenarios_router)
app.include_router(health_router)
app.include_router(history_router)

# Mount Target Demo Banking Sub-Application on /demo-app or embed endpoints
app.mount("/demo-target", demo_app)

# Ensure Frontend Static Dir exists
static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "public")
os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "service": "Botify Observability Demo Testing Platform",
        "status": "RUNNING",
        "docs": "/docs",
        "api_v1": "/api/v1/scenarios"
    }

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
