from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from datetime import datetime
import logging
import os
from pywebpush import webpush, WebPushException
import json
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env.local in parent directory
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(dotenv_path=env_path)

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
    allow_origin_regex=r"^https?://(" \
                       r"localhost|127\.0\.0\.1|" \
                       r"192\.168\.\d+\.\d+|" \
                       r"10\.\d+\.\d+\.\d+|" \
                       r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|" \
                       r"[a-zA-Z0-9-]+\.ngrok-free\.app|" \
                       r"[a-zA-Z0-9-]+\.ngrok-free\.dev|" \
                       r"[a-zA-Z0-9-]+\.ngrok\.io" \
                       r")(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)

# Store subscription in memory (in production, use a database)
subscription = None

class NotificationRequest(BaseModel):
    message: str

@app.get("/api/python")
def hello_world():
    return {"message": "Hello from FastAPI!"}

@app.post("/api/send-notification")
async def send_notification(req: NotificationRequest):
    """Send push notification to subscribed users"""
    global subscription
    try:
        if not req.message:
            raise HTTPException(status_code=400, detail="message is required")
        
        if not subscription:
            raise HTTPException(status_code=400, detail="No subscription available")
        
        # Get VAPID keys from environment
        vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        vapid_public_key = os.getenv("NEXT_PUBLIC_VAPID_PUBLIC_KEY")
        
        if not vapid_private_key or not vapid_public_key:
            raise HTTPException(status_code=500, detail="VAPID keys not configured")
        
        # Prepare notification payload
        notification_payload = json.dumps({
            "title": "Lottery Update",
            "body": req.message,
            "icon": "/web-app-manifest-192x192.png"
        })
        
        # Send push notification using pywebpush
        try:
            webpush(
                subscription_info=subscription,
                data=notification_payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={
                    "sub": "mailto:example@yourdomain.com"
                }
            )
            logger.info(f"Notification sent successfully: {req.message}")
            return {"success": True, "message": "Notification sent"}
        except WebPushException as e:
            logger.error(f"WebPush error: {e}")
            # If push fails due to expired subscription, clear it
            if e.response and e.response.status_code in [404, 410]:
                subscription = None
                raise HTTPException(status_code=410, detail="Subscription expired")
            raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/subscribe")
async def subscribe(data: dict):
    """Subscribe user to push notifications"""
    global subscription
    try:
        subscription = data
        logger.info("User subscribed to push notifications")
        return {"success": True, "message": "Subscribed successfully"}
    except Exception as e:
        logger.error(f"Subscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/unsubscribe")
async def unsubscribe():
    """Unsubscribe user from push notifications"""
    global subscription
    try:
        subscription = None
        logger.info("User unsubscribed from push notifications")
        return {"success": True, "message": "Unsubscribed successfully"}
    except Exception as e:
        logger.error(f"Unsubscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/extract")
async def extract_lottery_data(file: UploadFile = File(...)):
    """Extract lottery numbers from ticket image using OCR"""
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
            )
        
        # Read file content
        contents = await file.read()
        
        # TODO: Integrate with OCR library (Tesseract, PaddleOCR, etc.)
        # For now, return placeholder response
        logger.info(f"Processing image: {file.filename}")
        
        return {
            "status": "success",
            "extracted_data": {
                "game_type": "4D",
                "draw_date": datetime.now().strftime("%Y-%m-%d"),
                "numbers": [1, 2, 3, 4],
                "confidence": 0.95
            }
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Extract error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)