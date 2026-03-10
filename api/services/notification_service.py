"""
Notification Service for Lottery Results
Handles sending push notifications to users when their tickets are evaluated.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Dict, List
from urllib.parse import urlsplit
from pywebpush import WebPushException, webpush

try:
    from .supabase import get_supabase_client
    from ..schemas import UserSubscriptionCreate, UserSubscriptionUpdate
except ImportError:
    from services.supabase import get_supabase_client
    from schemas import UserSubscriptionCreate, UserSubscriptionUpdate

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for sending push notifications to users about lottery results.
    """

    def __init__(self):
        """Initialize the notification service."""
        self.supabase = get_supabase_client()
        self.vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        self.vapid_public_key = os.getenv("NEXT_PUBLIC_VAPID_PUBLIC_KEY")
        self.vapid_subject = os.getenv("VAPID_SUBJECT", "mailto:support@example.com")

    def _build_vapid_claims(self, subscription: Dict) -> Optional[Dict[str, str]]:
        """Build RFC-compliant VAPID claims from the subscription endpoint origin."""
        endpoint = subscription.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.strip():
            logger.error("Cannot send push notification: subscription endpoint is missing")
            return None

        parsed_endpoint = urlsplit(endpoint.strip())
        if not parsed_endpoint.scheme or not parsed_endpoint.netloc:
            logger.error("Cannot send push notification: invalid subscription endpoint '%s'", endpoint)
            return None

        return {
            "sub": self.vapid_subject,
            "aud": f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}",
        }

    def get_user_subscription(self, user_id: str) -> Optional[Dict]:
        """
        Retrieve user's push notification subscription from database.
        
        Args:
            user_id: User identifier
            
        Returns:
            Subscription data dict or None if not found
        """
        try:
            result = self.supabase.table("user_subscriptions").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0].get("subscription_data")
            return None
        except Exception as e:
            logger.error(f"Error fetching subscription for user {user_id}: {str(e)}")
            return None

    def save_user_subscription(self, user_id: str, subscription_data: Dict) -> bool:
        """
        Save or update user's push notification subscription.
        
        Args:
            user_id: User identifier
            subscription_data: Web Push subscription object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not user_id or not subscription_data:
                logger.error("Cannot save subscription: missing user_id or subscription_data")
                return False

            # Create schema instance
            subscription_schema = UserSubscriptionCreate(
                user_id=user_id,
                subscription_data=subscription_data,
                is_active=True
            )

            # Upsert subscription (update if exists, insert if not)
            self.supabase.table("user_subscriptions").upsert(
                subscription_schema.to_db_dict(),
                on_conflict="user_id"
            ).execute()
            
            logger.info(f"Saved subscription for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving subscription for user {user_id}: {str(e)}")
            return False

    def remove_user_subscription(self, user_id: str) -> bool:
        """
        Deactivate user's push notification subscription.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not user_id:
                logger.error("Cannot remove subscription: missing user_id")
                return False

            # Create update schema
            update_schema = UserSubscriptionUpdate(is_active=False)

            self.supabase.table("user_subscriptions").update(
                update_schema.to_db_dict()
            ).eq("user_id", user_id).execute()
            
            logger.info(f"Removed subscription for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error removing subscription for user {user_id}: {str(e)}")
            return False

    def send_push_notification(
        self,
        subscription: Dict,
        title: str,
        body: str,
        data: Optional[Dict] = None,
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Send a push notification to a specific subscription.
        
        Args:
            subscription: Web Push subscription object
            title: Notification title
            body: Notification body text
            data: Optional additional data to include
            user_id: Optional user identifier for logging / cleanup
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.vapid_private_key or not self.vapid_public_key:
            logger.error("VAPID keys not configured")
            return False

        vapid_claims = self._build_vapid_claims(subscription)
        if not vapid_claims:
            return False

        try:
            notification_payload = json.dumps({
                "title": title,
                "body": body,
                "icon": "/web-app-manifest-192x192.png",
                "badge": "/web-app-manifest-192x192.png",
                "data": data or {}
            })

            webpush(
                subscription_info=subscription,
                data=notification_payload,
                vapid_private_key=self.vapid_private_key,
                vapid_claims=vapid_claims,
            )
            
            logger.info("Push notification sent successfully: %s", title)
            return True
            
        except WebPushException as e:
            status_code = e.response.status_code if e.response else None
            response_body = ""
            if e.response is not None:
                try:
                    response_body = e.response.text or ""
                except Exception:
                    response_body = ""

            logger.error(
                "WebPush error for user %s: status=%s, body=%s, error=%s",
                user_id or "unknown",
                status_code or "unknown",
                (response_body[:500] if response_body else "<empty>"),
                str(e),
            )

            if status_code in [404, 410] and user_id:
                logger.warning("Deactivating expired push subscription for user %s", user_id)
                self.remove_user_subscription(user_id)
            elif status_code == 400:
                logger.warning(
                    "Push service returned 400 for user %s. Check VAPID claims/keys and re-subscribe the browser if keys were rotated.",
                    user_id or "unknown",
                )
            return False
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return False

    def notify_ticket_result(
        self,
        user_id: str,
        ticket_id: str,
        is_winner: bool,
        prize_tier: str,
        prize_amount: int,
        game_type: str,
        draw_date: str,
        draw_id: Optional[str] = None
    ) -> bool:
        """
        Send notification to user about their ticket evaluation result.
        
        Args:
            user_id: User identifier
            ticket_id: Ticket ID
            is_winner: Whether the ticket won
            prize_tier: Prize tier/category (e.g., "Group 1", "1st Prize", "No Prize")
            prize_amount: Prize amount in SGD
            game_type: Game type (4D or TOTO)
            draw_date: Draw date
            draw_id: Optional draw ID
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        # Get user's subscription
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            logger.info(f"No active subscription found for user {user_id}")
            return False

        # Compose notification message
        if is_winner:
            title = f"🎉 Congratulations! You Won!"
            body = f"{game_type} Draw - {prize_tier}: SGD ${prize_amount:,}"
        else:
            title = f"📋 {game_type} Results Available"
            body = f"Your ticket for {draw_date} did not win this time. Better luck next draw!"

        # Additional data for the notification
        notification_data = {
            "ticket_id": ticket_id,
            "is_winner": is_winner,
            "prize_tier": prize_tier,
            "prize_amount": prize_amount,
            "game_type": game_type,
            "draw_date": draw_date,
            "draw_id": draw_id,
            "url": f"/tickets/{ticket_id}"  # Link to ticket details page
        }

        # Send the notification
        return self.send_push_notification(
            subscription=subscription,
            title=title,
            body=body,
            data=notification_data,
            user_id=user_id,
        )

    def notify_batch_results(self, ticket_results: List[Dict]) -> Dict[str, int]:
        """
        Send notifications for a batch of evaluated tickets.
        
        Args:
            ticket_results: List of ticket evaluation results, each containing:
                - user_id
                - ticket_id
                - is_winner
                - prize_tier
                - prize_amount
                - game_type
                - draw_date
                - draw_id (optional)
        
        Returns:
            Summary dict with counts of successful/failed notifications
        """
        summary = {
            "total": len(ticket_results),
            "sent": 0,
            "failed": 0,
            "no_subscription": 0
        }

        for result in ticket_results:
            user_id = result.get("user_id")
            
            # Skip if no user_id (anonymous tickets)
            if not user_id:
                summary["no_subscription"] += 1
                continue

            success = self.notify_ticket_result(
                user_id=user_id,
                ticket_id=result.get("ticket_id"),
                is_winner=result.get("is_winner", False),
                prize_tier=result.get("prize_tier", "No Prize"),
                prize_amount=result.get("prize_amount", 0),
                game_type=result.get("game_type"),
                draw_date=result.get("draw_date"),
                draw_id=result.get("draw_id")
            )

            if success:
                summary["sent"] += 1
            else:
                summary["failed"] += 1

        logger.info(f"Batch notification summary: {summary}")
        return summary


def create_notification_service() -> NotificationService:
    """Factory function to create a NotificationService instance."""
    return NotificationService()
