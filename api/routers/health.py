from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "my-lottery-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/python")
def hello_world():
    return {"message": "Hello from FastAPI!"}
