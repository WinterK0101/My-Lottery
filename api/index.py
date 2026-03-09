from pathlib import Path
import os

from dotenv import load_dotenv

# Load environment variables from .env.local in parent directory FIRST
# This must be done before importing routers that need env vars
env_path = Path(__file__).parent.parent / ".env.local"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from .routers import extract, health, notifications, results, cron, tickets
except ImportError:
    from routers import extract, health, notifications, results, cron, tickets

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://("
    r"localhost|127\.0\.0\.1|"
    r"192\.168\.\d+\.\d+|"
    r"10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|"    r"[a-zA-Z0-9-]+\.vercel\.app|"    r"[a-zA-Z0-9-]+\.ngrok-free\.app|"
    r"[a-zA-Z0-9-]+\.ngrok-free\.dev|"
    r"[a-zA-Z0-9-]+\.ngrok\.io"
    r")(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(notifications.router)
app.include_router(extract.router)
app.include_router(results.router)
app.include_router(cron.router)
app.include_router(tickets.router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)