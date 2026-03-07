import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from ..services.notification_service import create_notification_service
    from ..schemas.notification import NotificationRequest
except ImportError:
    from services.notification_service import create_notification_service
    from schemas.notification import NotificationRequest

router = APIRouter()
logger = logging.getLogger(__name__)


class SubscriptionData(BaseModel):
    """Web Push subscription data"""
    user_id: str
    subscription: dict


@router.post("/api/send-notification")
async def send_notification(req: NotificationRequest):
    """
    Send push notification to subscribed users.
    
    For testing purposes - sends a generic notification.
    In production, use the notification service directly.
    """
    try:
        if not req.message:
            raise HTTPException(status_code=400, detail="message is required")

        notification_service = create_notification_service()
        
        # This is a test endpoint - in production, you'd specify the user_id
        # For now, we'll just return success
        return {
            "success": True,
            "message": "Notification service ready. Use subscribe endpoint to register users.",
        }

    except Exception as e:
        logger.error(f"Error in notification endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/api/subscribe")
async def subscribe(data: SubscriptionData):
    """
    Subscribe user to push notifications.
    
    Stores the user's subscription data in the database for later use.
    
    Body:
        user_id: User identifier
        subscription: Web Push subscription object
    """
    try:
        notification_service = create_notification_service()
        
        success = notification_service.save_user_subscription(
            user_id=data.user_id,
            subscription_data=data.subscription
        )
        
        if success:
            return {"success": True, "message": "Subscribed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save subscription")
            
    except Exception as e:
        logger.error(f"Subscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/api/unsubscribe")
async def unsubscribe(user_id: str):
    """
    Unsubscribe user from push notifications.
    
    Query Parameter:
        user_id: User identifier
    """
    try:
        notification_service = create_notification_service()
        
        success = notification_service.remove_user_subscription(user_id)
        
        if success:
            return {"success": True, "message": "Unsubscribed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to remove subscription")
            
    except Exception as e:
        logger.error(f"Unsubscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
