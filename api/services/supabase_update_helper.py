"""
Supabase Update Helper for Prize Matching Results
Provides SQL queries and Python helpers to update ticket statuses after evaluation.

Usage:
    from api.services.supabase_update_helper import (
        update_ticket_after_evaluation,
        bulk_update_tickets,
        update_ticket_status
    )
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

try:
    from ..services.supabase import get_supabase_client
except ImportError:
    from services.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def update_ticket_after_evaluation(
    ticket_id: str,
    evaluation_result: Dict,
) -> Dict[str, any]:
    """
    Update a single ticket in Supabase after evaluation.
    
    Args:
        ticket_id: The ticket UUID
        evaluation_result: Result from evaluate_ticket() function
    
    Returns:
        Dict with update status
    
    Example:
        evaluation = {
            "game_type": "TOTO",
            "prize_tier": "Group 1",
            "is_winner": True,
            "matched_numbers": [1, 2, 3, 4, 5, 6],
            ...
        }
        result = update_ticket_after_evaluation("ticket-uuid", evaluation)
        print(result)
        # {"status": "updated", "ticket_id": "...", "new_status": "won"}
    """
    try:
        supabase = get_supabase_client()
        
        is_winner = evaluation_result.get("is_winner", False)
        prize_tier = evaluation_result.get("prize_tier", "No Prize")
        
        # Prepare update data
        update_data = {
            "status": "won" if is_winner else "lost",
            "prize_tier": prize_tier,
            "evaluation_result": evaluation_result,
            "evaluated_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Execute update
        response = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        
        if not response.data:
            logger.warning(f"No ticket found with ID: {ticket_id}")
            return {
                "status": "not_found",
                "ticket_id": ticket_id,
                "message": "Ticket not found in database"
            }
        
        logger.info(f"Ticket {ticket_id} updated to {update_data['status']}")
        
        return {
            "status": "updated",
            "ticket_id": ticket_id,
            "new_status": update_data["status"],
            "prize_tier": prize_tier,
        }
    
    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id}: {str(e)}")
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "message": str(e)
        }


def bulk_update_tickets(
    updates: List[Dict],
) -> Dict[str, any]:
    """
    Update multiple tickets in batch.
    
    Args:
        updates: List of dicts with:
            {
                "ticket_id": "uuid",
                "evaluation_result": {...evaluation dict...}
            }
    
    Returns:
        Summary of updates
    
    Example:
        updates = [
            {
                "ticket_id": "ticket-1",
                "evaluation_result": {"game_type": "4D", "prize_tier": "1st Prize", ...}
            },
            {
                "ticket_id": "ticket-2",
                "evaluation_result": {"game_type": "TOTO", "prize_tier": "Group 1", ...}
            }
        ]
        result = bulk_update_tickets(updates)
        print(result)
        # {"status": "bulk_update_completed", "total": 2, "successful": 2, "failed": 0}
    """
    successful = 0
    failed = 0
    errors = []
    
    for update in updates:
        ticket_id = update.get("ticket_id")
        evaluation_result = update.get("evaluation_result")
        
        if not ticket_id or not evaluation_result:
            failed += 1
            errors.append(f"Missing ticket_id or evaluation_result: {update}")
            continue
        
        result = update_ticket_after_evaluation(ticket_id, evaluation_result)
        
        if result.get("status") == "updated":
            successful += 1
        else:
            failed += 1
            errors.append(f"{ticket_id}: {result.get('message')}")
    
    return {
        "status": "bulk_update_completed",
        "total": len(updates),
        "successful": successful,
        "failed": failed,
        "errors": errors if errors else None,
    }


def update_ticket_status(
    ticket_id: str,
    status: str,
    prize_tier: Optional[str] = None,
) -> Dict[str, any]:
    """
    Manually update ticket status (lower-level function).
    
    Args:
        ticket_id: The ticket UUID
        status: One of "pending", "won", "lost", "evaluated", "error"
        prize_tier: Prize tier string (e.g., "1st Prize", "Group 1")
    
    Returns:
        Update result
    
    Note: Prefer update_ticket_after_evaluation() which auto-determines status
    """
    try:
        supabase = get_supabase_client()
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        if prize_tier:
            update_data["prize_tier"] = prize_tier
        
        response = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
        
        if not response.data:
            return {
                "status": "not_found",
                "ticket_id": ticket_id,
            }
        
        return {
            "status": "updated",
            "ticket_id": ticket_id,
            "new_status": status,
        }
    
    except Exception as e:
        logger.error(f"Error updating status for {ticket_id}: {str(e)}")
        return {
            "status": "error",
            "ticket_id": ticket_id,
            "message": str(e)
        }


def get_pending_tickets(
    game_type: Optional[str] = None,
    draw_date: Optional[str] = None,
    limit: int = 100,
) -> List[Dict]:
    """
    Query pending tickets that need evaluation.
    
    Args:
        game_type: Filter by "4D" or "TOTO" (optional)
        draw_date: Filter by draw date YYYY-MM-DD (optional)
        limit: Maximum results to return
    
    Returns:
        List of pending ticket records
    
    Example:
        # Get all pending 4D tickets for today
        from datetime import date
        today = str(date.today())
        tickets = get_pending_tickets(game_type="4D", draw_date=today)
        print(f"Found {len(tickets)} pending 4D tickets")
        
        # Get all pending TOTO tickets
        tickets = get_pending_tickets(game_type="TOTO")
    """
    try:
        supabase = get_supabase_client()
        
        query = supabase.table("tickets").select("*").eq("status", "pending")
        
        if game_type:
            query = query.eq("game_type", game_type)
        
        if draw_date:
            query = query.eq("draw_date", draw_date)
        
        query = query.limit(limit)
        
        response = query.execute()
        
        return response.data if response.data else []
    
    except Exception as e:
        logger.error(f"Error querying pending tickets: {str(e)}")
        return []


def get_winning_tickets(
    game_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """
    Query winning tickets.
    
    Args:
        game_type: Filter by "4D" or "TOTO" (optional)
        limit: Maximum results to return
    
    Returns:
        List of winning ticket records
    
    Example:
        winning = get_winning_tickets(game_type="TOTO")
        for ticket in winning:
            print(f"Ticket {ticket['id']}: {ticket['prize_tier']}")
    """
    try:
        supabase = get_supabase_client()
        
        query = supabase.table("tickets").select("*").eq("status", "won")
        
        if game_type:
            query = query.eq("game_type", game_type)
        
        response = query.limit(limit).order("evaluated_at", desc=True).execute()
        
        return response.data if response.data else []
    
    except Exception as e:
        logger.error(f"Error querying winning tickets: {str(e)}")
        return []


# ============================================================================
# SQL Queries (for reference / direct database access)
# ============================================================================

SQL_REFERENCE = """
================================================================================
DIRECT SQL QUERIES FOR TICKET UPDATES
================================================================================

See SQL queries below to understand what's happening behind the scenes.

-- UPDATE AFTER EVALUATION (won)
UPDATE tickets SET
    status = 'won',
    prize_tier = 'Group 1',
    evaluation_result = '{"game_type": "TOTO", "prize_tier": "Group 1", ...}'::jsonb,
    evaluated_at = NOW(),
    updated_at = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';

-- UPDATE AFTER EVALUATION (lost)
UPDATE tickets SET
    status = 'lost',
    prize_tier = 'No Prize',
    evaluation_result = '{"game_type": "TOTO", "prize_tier": "No Prize", ...}'::jsonb,
    evaluated_at = NOW(),
    updated_at = NOW()
WHERE id = '550e8400-e29b-41d4-a716-446655440000';

-- GET ALL PENDING TICKETS TODAY
SELECT 
    id,
    game_type,
    ticket_type,
    selected_numbers,
    combinations_count,
    created_at
FROM tickets
WHERE 
    status = 'pending'
    AND draw_date = CURRENT_DATE
ORDER BY created_at DESC;

-- GET ALL WINNING TICKETS (TOTO)
SELECT 
    id,
    user_id,
    prize_tier,
    game_type,
    ticket_type,
    selected_numbers,
    combinations_count,
    evaluated_at
FROM tickets
WHERE 
    status = 'won'
    AND game_type = 'TOTO'
ORDER BY evaluated_at DESC
LIMIT 20;

-- GET ALL LOSING TICKETS (TODAY)
SELECT 
    id,
    game_type,
    prize_tier,
    evaluated_at
FROM tickets
WHERE 
    status = 'lost'
    AND draw_date = CURRENT_DATE
ORDER BY evaluated_at DESC;

-- COUNT STATISTICS
SELECT 
    game_type,
    status,
    COUNT(*) as count
FROM tickets
WHERE draw_date = CURRENT_DATE
GROUP BY game_type, status;

-- GET RESULTS SUMMARY FOR A DAY
SELECT
    draw_date,
    game_type,
    CASE WHEN status = 'won' THEN 'Winners' ELSE status END as result,
    COUNT(*) as count,
    COUNT(DISTINCT user_id) as unique_users
FROM tickets
WHERE draw_date = '2026-03-06'
GROUP BY draw_date, game_type, status
ORDER BY draw_date, game_type, status;

-- UPDATE MULTIPLE TICKETS AT ONCE
UPDATE tickets SET
    status = 'lost',
    prize_tier = 'No Prize',
    evaluated_at = NOW(),
    updated_at = NOW()
WHERE 
    draw_date = CURRENT_DATE
    AND status = 'pending'
    AND game_type = '4D';

-- DELETE EVALUATION DATA (for re-testing)
UPDATE tickets SET
    status = 'pending',
    prize_tier = NULL,
    evaluation_result = NULL,
    evaluated_at = NULL
WHERE draw_date = '2026-03-06';

================================================================================
"""
