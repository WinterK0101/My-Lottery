from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/api/python")
def hello_world():
    return {"message": "Hello from FastAPI!"}

# Add OCR and Prediction endpoints here