import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pywebpush import WebPushException, webpush

try:
    from ..schemas.notification import NotificationRequest
except ImportError:
    from schemas.notification import NotificationRequest

router = APIRouter()
logger = logging.getLogger(__name__)

# Store subscription in memory (in production, use a database)
subscription = None


@router.post("/api/send-notification")
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
        notification_payload = json.dumps(
            {
                "title": "Lottery Update",
                "body": req.message,
                "icon": "/web-app-manifest-192x192.png",
            }
        )

        # Send push notification using pywebpush
        try:
            webpush(
                subscription_info=subscription,
                data=notification_payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={"sub": "mailto:notify@lottery-app.local"},
            )
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


@router.post("/api/subscribe")
async def subscribe(data: dict):
    """Subscribe user to push notifications"""
    global subscription
    try:
        subscription = data
        return {"success": True, "message": "Subscribed successfully"}
    except Exception as e:
        logger.error(f"Subscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/api/unsubscribe")
async def unsubscribe():
    """Unsubscribe user from push notifications"""
    global subscription
    try:
        subscription = None
        return {"success": True, "message": "Unsubscribed successfully"}
    except Exception as e:
        logger.error(f"Unsubscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
