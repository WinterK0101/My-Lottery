"""
Pydantic schemas for notifications and user_subscriptions table
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class NotificationRequest(BaseModel):
    """Schema for notification request"""
    message: str


class UserSubscriptionCreate(BaseModel):
    """Schema for creating/updating user subscription"""
    user_id: str = Field(..., description="User identifier")
    subscription_data: Dict[str, Any] = Field(..., description="Web Push subscription object")
    is_active: bool = Field(default=True, description="Whether subscription is active")

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database insertion"""
        return {
            "user_id": self.user_id,
            "subscription_data": self.subscription_data,
            "is_active": self.is_active,
            "updated_at": datetime.utcnow().isoformat(),
        }


class UserSubscriptionUpdate(BaseModel):
    """Schema for updating user subscription"""
    is_active: bool = Field(..., description="Whether subscription is active")

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database update"""
        return {
            "is_active": self.is_active,
            "updated_at": datetime.utcnow().isoformat(),
        }


class UserSubscriptionResponse(BaseModel):
    """Schema for user subscription response from database"""
    id: str
    user_id: str
    subscription_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True
