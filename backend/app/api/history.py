import os
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from backend.app.core.history_store import history_store
from backend.app.config import settings

router = APIRouter(prefix="/api/v1/history", tags=["Execution History"])

@router.get("")
def get_history(limit: int = Query(50, ge=1, le=500)):
    return {"history": history_store.get_history(limit=limit)}

@router.post("/clear")
def clear_history():
    history_store.clear_history()
    return {"status": "success", "message": "Execution audit history cleared."}

@router.get("/download-csv")
def download_splunk_csv():
    csv_path = getattr(settings, "SPLUNK_CSV_FILE_PATH", "./data/logs/splunk_events.csv")
    if os.path.exists(csv_path):
        return FileResponse(
            path=csv_path,
            filename="splunk_events.csv",
            media_type="text/csv"
        )
    raise HTTPException(status_code=404, detail="Splunk events CSV log file not found.")
