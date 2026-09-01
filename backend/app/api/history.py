from fastapi import APIRouter, Query
from backend.app.core.history_store import history_store

router = APIRouter(prefix="/api/v1/history", tags=["Execution History"])

@router.get("")
def get_history(limit: int = Query(50, ge=1, le=500)):
    return {"history": history_store.get_history(limit=limit)}

@router.post("/clear")
def clear_history():
    history_store.clear_history()
    return {"status": "success", "message": "Execution audit history cleared."}
