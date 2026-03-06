from fastapi import APIRouter

router = APIRouter()


@router.get("/api/python")
def hello_world():
    return {"message": "Hello from FastAPI!"}
