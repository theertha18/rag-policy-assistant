from fastapi import APIRouter, HTTPException, Request

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness: is the process running?")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness: can it answer questions right now?")
def ready(request: Request) -> dict:
    try:
        count = request.app.state.store.count()
    except Exception:
        raise HTTPException(status_code=503, detail="Vector store unreachable")
    if count == 0:
        raise HTTPException(status_code=503, detail="No documents ingested")
    return {"status": "ready", "chunks": count}